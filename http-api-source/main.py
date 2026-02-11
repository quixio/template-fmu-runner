import os
import json
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import Flask, request, redirect, abort, jsonify, send_file, send_from_directory
from flasgger import Swagger
from waitress import serve
from functools import wraps

from flask_cors import CORS

from setup_logging import get_logger
from quixstreams import Application
from datalake_query import DataLakeQuery

# Directory for stored models - use state directory if available (persists across restarts)
STATE_DIR = Path(os.environ.get("state_dir", "state"))
MODELS_DIR = STATE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Frontend static files directory
FRONTEND_DIR = Path(__file__).parent / "frontend"

# Model retention period (24 hours)
MODEL_RETENTION_HOURS = 24

# for local dev, load env vars from a .env file
from dotenv import load_dotenv
load_dotenv()

service_url = os.environ.get("Quix__Deployment__Network__PublicUrl", "http://localhost:80")

quix_app = Application()
topic = quix_app.topic(os.environ.get("output", "simulation"))
producer = quix_app.get_producer()

logger = get_logger()

# Initialize data lake query helper
datalake = DataLakeQuery()

app = Flask(__name__)

# Enable CORS for all routes and origins by default
CORS(app)

app.config['SWAGGER'] = {
    'title': 'Simulation API',
    'description': 'API for submitting Simulink simulation configurations to Kafka.',
    'uiversion': 3
}

swagger = Swagger(app)


# Serve frontend static files
@app.route('/')
def serve_frontend():
    """Serve the frontend application."""
    if FRONTEND_DIR.exists():
        index_path = FRONTEND_DIR / 'index.html'
        if index_path.exists():
            # Inject runtime config into the HTML
            with open(index_path, 'r') as f:
                html = f.read()
            # Replace placeholders with actual values
            auth_token = os.environ.get('HTTP_AUTH_TOKEN', '')
            html = html.replace('__RUNTIME_API_URL__', '/simulation')
            html = html.replace('__RUNTIME_HTTP_AUTH_TOKEN__', auth_token)
            return html, 200, {'Content-Type': 'text/html'}
    return "Frontend not available", 404


@app.route('/assets/<path:path>')
def serve_assets(path):
    """Serve static assets from the frontend directory."""
    if FRONTEND_DIR.exists():
        return send_from_directory(FRONTEND_DIR / 'assets', path)
    return "Not found", 404


def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            abort(401, "Missing or malformed Authorization header")
        if auth_header.split(" ", 1)[1] != os.environ["HTTP_AUTH_TOKEN"]:
            abort(403, "Invalid token")
        return func(*args, **kwargs)
    return wrapper


def generate_message_key(model_filename: str) -> str:
    """Generate a message key in the format: 2024-02-02T12:30:00_model-name.slx"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{timestamp}_{model_filename}"


def cleanup_old_models():
    """Delete models older than MODEL_RETENTION_HOURS."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MODEL_RETENTION_HOURS)
    deleted_count = 0

    for model_path in MODELS_DIR.glob("*"):
        if model_path.is_file():
            # Use file modification time for age check
            mtime = datetime.fromtimestamp(model_path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                model_path.unlink()
                deleted_count += 1
                logger.info(f"Deleted old model: {model_path.name}")

    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old model(s)")


def store_model(filename: str, data_base64: str) -> Path:
    """
    Store a model file to disk from base64-encoded data.

    Args:
        filename: Original filename of the model
        data_base64: Base64-encoded model binary

    Returns:
        Path: Path to the stored model file
    """
    model_path = MODELS_DIR / filename
    model_bytes = base64.b64decode(data_base64)
    model_path.write_bytes(model_bytes)
    logger.info(f"Stored model: {filename} ({len(model_bytes)} bytes)")
    return model_path




@app.route("/simulation", methods=['POST'])
@require_auth
def post_simulation():
    """
    Submit an FMU simulation configuration
    ---
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - model_filename
            - input_data
            - config
          properties:
            model_filename:
              type: string
              description: Name of the FMU file
              example: "BouncingBall.fmu"
            model_data:
              type: string
              description: Base64-encoded FMU binary (optional if model already exists on server)
            input_data:
              type: array
              description: Input data rows (converted from CSV)
              items:
                type: object
              example: [{"time": "0.0", "input1": "1.0"}, {"time": "1.0", "input1": "2.0"}]
            config:
              type: object
              description: Simulation configuration including success_criteria
              example: {"start_time": 0, "stop_time": 10, "parameters": {}, "success_criteria": {"field_name": "h", "target_value": 1.0}}
    responses:
      200:
        description: Simulation submitted successfully
        schema:
          type: object
          properties:
            status:
              type: string
              example: "submitted"
            message_key:
              type: string
              example: "2024-02-02T12:30:00_BouncingBall.fmu"
      400:
        description: Invalid request payload
      401:
        description: Missing or malformed Authorization header
      403:
        description: Invalid token
    """
    data = request.json

    # Validate required fields
    required_fields = ['model_filename', 'input_data', 'config']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    model_filename = data['model_filename']
    model_path = MODELS_DIR / model_filename

    # If data is provided, store the new model
    # If data is not provided, check if model already exists on disk
    if data.get('model_data'):
        store_model(model_filename, data['model_data'])
    elif not model_path.exists():
        return jsonify({"error": f"Model not found: {model_filename}. Please upload the model file."}), 400
    else:
        logger.info(f"Using existing model: {model_filename}")

    # Generate message key
    message_key = generate_message_key(model_filename)

    # Add metadata to payload - only pass model reference, not the binary data
    payload = {
        "message_key": message_key,
        "submitted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model_filename": model_filename,
        # Note: 'model_data' field is intentionally omitted - services fetch via API
        "input_data": data['input_data'],
        "config": data['config'],
        "source": "user"  # Flag to indicate user-initiated (vs system-initiated retries)
    }

    logger.debug(f"Submitting simulation: {message_key}")
    logger.debug(f"Model: {model_filename} (stored to disk), Input rows: {len(data['input_data'])}")

    # Publish to Kafka
    producer.produce(
        topic.name,
        json.dumps(payload),
        message_key.encode()
    )

    logger.info(f"Simulation submitted: {message_key}")

    return jsonify({
        "status": "submitted",
        "message_key": message_key
    }), 200


@app.route("/health", methods=['GET'])
def health_check():
    """
    Health check endpoint
    ---
    responses:
      200:
        description: Service is healthy
    """
    return jsonify({"status": "healthy"}), 200


@app.route("/models/<filename>", methods=['GET'])
@require_auth
def get_model(filename):
    """
    Retrieve a stored model file
    ---
    parameters:
      - in: path
        name: filename
        type: string
        required: true
        description: The filename of the model to retrieve
    responses:
      200:
        description: Model file binary
        content:
          application/octet-stream:
            schema:
              type: string
              format: binary
      404:
        description: Model not found
      401:
        description: Missing or malformed Authorization header
      403:
        description: Invalid token
    """
    model_path = MODELS_DIR / filename

    if not model_path.exists():
        return jsonify({"error": f"Model not found: {filename}"}), 404

    logger.debug(f"Serving model: {filename}")
    return send_file(model_path, mimetype='application/octet-stream', as_attachment=True, download_name=filename)


@app.route("/models/<filename>/metadata", methods=['GET'])
@require_auth
def get_model_metadata(filename):
    """
    Get metadata for an FMU model file (inputs, outputs, parameters)
    ---
    parameters:
      - in: path
        name: filename
        type: string
        required: true
        description: The filename of the FMU model
    responses:
      200:
        description: FMU metadata including inputs, outputs, and parameters
      404:
        description: Model not found
      400:
        description: Not an FMU file
      401:
        description: Missing or malformed Authorization header
      403:
        description: Invalid token
    """
    model_path = MODELS_DIR / filename

    if not model_path.exists():
        return jsonify({"error": f"Model not found: {filename}"}), 404

    # Only process FMU files
    if not filename.lower().endswith('.fmu'):
        return jsonify({
            "model_type": "simulink",
            "message": "Metadata extraction only available for FMU files"
        }), 200

    try:
        from fmpy import read_model_description

        md = read_model_description(str(model_path))

        def get_type_name(fmu_type):
            """Extract type name string from FMU type object."""
            if fmu_type is None:
                return 'Real'
            type_name = type(fmu_type).__name__
            if type_name in ('Real', 'Integer', 'Boolean', 'String'):
                return type_name
            return 'Real'

        # Categorize variables by causality
        variables = {
            'inputs': [],
            'outputs': [],
            'parameters': [],
            'local': [],
            'other': []
        }

        for v in md.modelVariables:
            var_info = {
                'name': v.name,
                'valueReference': v.valueReference,
                'description': v.description or '',
                'type': get_type_name(v.type),
                'start': getattr(v, 'start', None),
                'causality': v.causality,
                'variability': getattr(v, 'variability', None),
            }

            if v.causality == 'input':
                variables['inputs'].append(var_info)
            elif v.causality == 'output':
                variables['outputs'].append(var_info)
            elif v.causality == 'parameter':
                variables['parameters'].append(var_info)
            elif v.causality == 'local':
                variables['local'].append(var_info)
            else:
                variables['other'].append(var_info)

        model_info = {
            'model_type': 'fmu',
            'modelName': md.modelName,
            'fmiVersion': md.fmiVersion,
            'description': md.description or '',
            'generationTool': getattr(md, 'generationTool', '') or '',
        }

        return jsonify({
            'success': True,
            'modelInfo': model_info,
            'variables': variables
        }), 200

    except Exception as e:
        logger.error(f"Failed to read FMU metadata: {e}")
        return jsonify({"error": f"Failed to read FMU metadata: {str(e)}"}), 500


@app.route("/runs/<message_key>", methods=['GET'])
@require_auth
def get_run_details(message_key):
    """
    Get details for a specific simulation run
    ---
    parameters:
      - in: path
        name: message_key
        type: string
        required: true
        description: The message key of the simulation run
    responses:
      200:
        description: Run details including result, timeseries, and statistics
      404:
        description: Run not found
      401:
        description: Missing or malformed Authorization header
      403:
        description: Invalid token
    """
    # Use get_related_runs as primary source to work around QuixLake catalog inconsistency
    # The catalog sometimes returns different file lists for concurrent queries
    related_runs = datalake.get_related_runs(message_key)

    # Find the specific record in the related runs
    result = next((r for r in related_runs if r.get('message_key') == message_key), None)

    # Fallback to direct query if not found in related runs
    if not result:
        result = datalake.get_result_by_message_key(message_key)

    if not result:
        return jsonify({"error": f"Run not found: {message_key}"}), 404

    timeseries = datalake.get_timeseries_by_message_key(message_key)
    statistics = datalake.compute_statistics(timeseries)

    return jsonify({
        "result": result,
        "timeseries": timeseries,
        "statistics": statistics
    }), 200


@app.route("/runs/<message_key>/result", methods=['GET'])
@require_auth
def get_run_result(message_key):
    """
    Get the result/validation data for a run family.
    If the original run failed but a variant passed, returns the best passing variant.
    ---
    parameters:
      - in: path
        name: message_key
        type: string
        required: true
    responses:
      200:
        description: Run result data (best result from family)
      404:
        description: Run not found
    """
    # Use family result to get the best outcome from the run family
    result = datalake.get_family_result(message_key)

    if not result:
        return jsonify({"error": f"Run not found: {message_key}"}), 404

    return jsonify(result), 200


@app.route("/runs/<message_key>/timeseries", methods=['GET'])
@require_auth
def get_run_timeseries(message_key):
    """
    Get timeseries data for a run
    ---
    parameters:
      - in: path
        name: message_key
        type: string
        required: true
    responses:
      200:
        description: Timeseries data array
    """
    timeseries = datalake.get_timeseries_by_message_key(message_key)
    return jsonify(timeseries), 200


@app.route("/runs/<message_key>/related", methods=['GET'])
@require_auth
def get_related_runs(message_key):
    """
    Get all runs related to a message_key (parent and generated variations)
    ---
    parameters:
      - in: path
        name: message_key
        type: string
        required: true
        description: The message key of any run in the family
    responses:
      200:
        description: List of related runs with their results
        schema:
          type: object
          properties:
            runs:
              type: array
              items:
                type: object
            parent_key:
              type: string
              description: The original parent run's message_key
      404:
        description: No related runs found
      401:
        description: Missing or malformed Authorization header
      403:
        description: Invalid token
    """
    runs = datalake.get_related_runs(message_key)

    if not runs:
        return jsonify({"error": f"No related runs found for: {message_key}"}), 404

    # Determine which is the parent (no _gen_ suffix)
    parent_key = message_key
    if "_gen_" in message_key:
        parent_key = message_key.rsplit("_gen_", 1)[0]

    # Find the parent run to extract original config
    parent_run = next((r for r in runs if r.get('message_key') == parent_key), None)

    return jsonify({
        "runs": runs,
        "parent_key": parent_key,
        "parent_run": parent_run
    }), 200


if __name__ == '__main__':
    # Cleanup old models on startup
    cleanup_old_models()

    print("=" * 60)
    print(" " * 15 + "SIMULATION API")
    print("=" * 60)
    print(f"Model storage: {MODELS_DIR}")
    print(f"Model retention: {MODEL_RETENTION_HOURS} hours")
    print(
        f"""
Submit an FMU simulation:

curl -L -X POST \\
    -H 'Content-Type: application/json' \\
    -H 'Authorization: Bearer $HTTP_AUTH_TOKEN' \\
    -d '{{
        "model_filename": "BouncingBall.fmu",
        "model_data": "<base64>",
        "input_data": [{{"time": "0.0"}}],
        "config": {{
            "start_time": 0,
            "stop_time": 10,
            "parameters": {{}},
            "success_criteria": {{
                "field_name": "h",
                "target_value": 1.0
            }}
        }}
    }}' \\
    {service_url}/simulation
    """
    )
    print("=" * 60)

    serve(app, host="0.0.0.0", port=80)
