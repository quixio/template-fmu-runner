import os
import json
import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, redirect, abort, jsonify, send_from_directory
from flasgger import Swagger
from waitress import serve
from functools import wraps

import boto3
from botocore.client import Config

from flask_cors import CORS

from setup_logging import get_logger
from quixstreams import Application
from datalake_query import DataLakeQuery

# Frontend static files directory
FRONTEND_DIR = Path(__file__).parent / "frontend"

# S3 Configuration
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.environ.get("S3_BUCKET", "fmu-models")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    config=Config(signature_version='s3v4')
)

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


def ensure_bucket_exists():
    """Ensure the S3 bucket exists, create if not."""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
    except Exception:
        try:
            s3_client.create_bucket(Bucket=S3_BUCKET)
            logger.info(f"Created S3 bucket: {S3_BUCKET}")
        except Exception as e:
            logger.warning(f"Could not create bucket (may already exist): {e}")


def extract_fmu_metadata(fmu_bytes: bytes, filename: str) -> dict:
    """
    Extract metadata from FMU binary.

    Args:
        fmu_bytes: FMU file binary content
        filename: Original filename

    Returns:
        dict: Metadata including inputs, outputs, parameters
    """
    import tempfile
    from fmpy import read_model_description

    # Write to temp file for fmpy to read
    with tempfile.NamedTemporaryFile(suffix='.fmu', delete=False) as tmp:
        tmp.write(fmu_bytes)
        tmp_path = tmp.name

    try:
        md = read_model_description(tmp_path)

        def get_type_name(fmu_type):
            if fmu_type is None:
                return 'Real'
            type_name = type(fmu_type).__name__
            if type_name in ('Real', 'Integer', 'Boolean', 'String'):
                return type_name
            return 'Real'

        variables = {
            'inputs': [],
            'outputs': [],
            'parameters': []
        }

        for v in md.modelVariables:
            var_info = {
                'name': v.name,
                'type': get_type_name(v.type),
                'start': getattr(v, 'start', None),
                'description': v.description or ''
            }

            if v.causality == 'input':
                variables['inputs'].append(var_info)
            elif v.causality == 'output':
                variables['outputs'].append(var_info)
            elif v.causality == 'parameter':
                variables['parameters'].append(var_info)

        return {
            'filename': filename,
            'modelName': md.modelName,
            'fmiVersion': md.fmiVersion,
            'description': md.description or '',
            'generationTool': getattr(md, 'generationTool', '') or '',
            'variables': variables
        }
    finally:
        os.unlink(tmp_path)


def store_model_to_s3(filename: str, data_base64: str) -> dict:
    """
    Store a model file and its metadata to S3.

    Args:
        filename: Original filename of the model
        data_base64: Base64-encoded model binary

    Returns:
        dict: Contains 'model_s3_path' and 'metadata_s3_path'
    """
    ensure_bucket_exists()

    model_bytes = base64.b64decode(data_base64)
    file_hash = hashlib.sha256(model_bytes).hexdigest()[:16]

    # S3 keys
    model_key = f"models/{file_hash}_{filename}"
    metadata_key = f"models/{file_hash}_{filename}.metadata.json"

    # Check if model already exists
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=model_key)
        logger.info(f"Model already exists in S3: {model_key}")
    except Exception:
        # Upload model
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=model_key,
            Body=model_bytes,
            ContentType='application/octet-stream'
        )
        logger.info(f"Uploaded model to S3: {model_key} ({len(model_bytes)} bytes)")

    # Extract and upload metadata for FMU files
    if filename.lower().endswith('.fmu'):
        try:
            metadata = extract_fmu_metadata(model_bytes, filename)
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=metadata_key,
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json'
            )
            logger.info(f"Uploaded metadata to S3: {metadata_key}")
        except Exception as e:
            logger.warning(f"Failed to extract/upload FMU metadata: {e}")
            metadata_key = None

    return {
        'model_s3_path': model_key,
        'metadata_s3_path': metadata_key
    }


def get_model_s3_path(filename: str) -> str:
    """
    Find an existing model in S3 by filename.

    Args:
        filename: Original filename to search for

    Returns:
        str: S3 key if found, None otherwise
    """
    try:
        # List objects with the models/ prefix and look for matching filename
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix='models/'
        )

        for obj in response.get('Contents', []):
            key = obj['Key']
            # Key format: models/{hash}_{filename}
            if key.endswith(f'_{filename}') and not key.endswith('.metadata.json'):
                return key

        return None
    except Exception as e:
        logger.error(f"Error searching for model in S3: {e}")
        return None




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
              description: Base64-encoded FMU binary (optional if model already exists in S3)
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
            model_s3_path:
              type: string
              example: "models/abc123_BouncingBall.fmu"
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
    model_s3_path = None
    metadata_s3_path = None

    # If data is provided, store the new model to S3
    # If data is not provided, check if model already exists in S3
    if data.get('model_data'):
        s3_result = store_model_to_s3(model_filename, data['model_data'])
        model_s3_path = s3_result['model_s3_path']
        metadata_s3_path = s3_result.get('metadata_s3_path')
    else:
        # Look for existing model in S3
        model_s3_path = get_model_s3_path(model_filename)
        if not model_s3_path:
            return jsonify({"error": f"Model not found: {model_filename}. Please upload the model file."}), 400
        logger.info(f"Using existing model from S3: {model_s3_path}")

    # Generate message key
    message_key = generate_message_key(model_filename)

    # Add metadata to payload - pass S3 path for direct fetching
    payload = {
        "message_key": message_key,
        "submitted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model_filename": model_filename,
        "model_s3_path": model_s3_path,  # S3 key for direct fetching
        "input_data": data['input_data'],
        "config": data['config'],
        "source": "user"  # Flag to indicate user-initiated (vs system-initiated retries)
    }

    logger.debug(f"Submitting simulation: {message_key}")
    logger.debug(f"Model: {model_filename} (S3: {model_s3_path}), Input rows: {len(data['input_data'])}")

    # Publish to Kafka
    producer.produce(
        topic.name,
        json.dumps(payload),
        message_key.encode()
    )

    logger.info(f"Simulation submitted: {message_key}")

    return jsonify({
        "status": "submitted",
        "message_key": message_key,
        "model_s3_path": model_s3_path,
        "metadata_s3_path": metadata_s3_path
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


@app.route("/poc/minio-test", methods=['GET'])
def poc_minio_test():
    """
    POC: Test MinIO write/read for datalake bucket
    ---
    responses:
      200:
        description: MinIO read/write test results
    """
    from datetime import datetime

    # Use datalake bucket (same as the sink uses)
    datalake_bucket = "datalake"
    test_key = f"poc-test/test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    test_content = f"Hello from POC test at {datetime.now().isoformat()}"

    results = {
        "endpoint": S3_ENDPOINT,
        "bucket": datalake_bucket,
        "test_key": test_key,
        "steps": []
    }

    try:
        # Step 1: Ensure bucket exists
        try:
            s3_client.head_bucket(Bucket=datalake_bucket)
            results["steps"].append({"step": "check_bucket", "status": "exists"})
        except Exception:
            s3_client.create_bucket(Bucket=datalake_bucket)
            results["steps"].append({"step": "create_bucket", "status": "created"})

        # Step 2: Write test file
        s3_client.put_object(
            Bucket=datalake_bucket,
            Key=test_key,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain'
        )
        results["steps"].append({"step": "write", "status": "success", "bytes": len(test_content)})

        # Step 3: Read it back
        response = s3_client.get_object(Bucket=datalake_bucket, Key=test_key)
        read_content = response['Body'].read().decode('utf-8')
        results["steps"].append({"step": "read", "status": "success", "content": read_content})

        # Step 4: Verify content matches
        if read_content == test_content:
            results["steps"].append({"step": "verify", "status": "match"})
        else:
            results["steps"].append({"step": "verify", "status": "mismatch"})

        # Step 5: List objects in bucket (show what's there)
        list_response = s3_client.list_objects_v2(Bucket=datalake_bucket, MaxKeys=10)
        objects = [{"key": obj["Key"], "size": obj["Size"]} for obj in list_response.get("Contents", [])]
        results["steps"].append({"step": "list", "status": "success", "objects": objects})

        # Step 6: Clean up test file
        s3_client.delete_object(Bucket=datalake_bucket, Key=test_key)
        results["steps"].append({"step": "cleanup", "status": "deleted"})

        results["success"] = True

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"POC MinIO test failed: {e}")

    return jsonify(results), 200 if results.get("success") else 500


@app.route("/models/<path:s3_path>/metadata", methods=['GET'])
@require_auth
def get_model_metadata_from_s3(s3_path):
    """
    Get metadata for an FMU model from S3
    ---
    parameters:
      - in: path
        name: s3_path
        type: string
        required: true
        description: The S3 path of the FMU model (e.g., models/abc123_BouncingBall.fmu)
    responses:
      200:
        description: FMU metadata including inputs, outputs, and parameters
      404:
        description: Metadata not found
      401:
        description: Missing or malformed Authorization header
      403:
        description: Invalid token
    """
    # Construct metadata key from model path
    metadata_key = f"{s3_path}.metadata.json"

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=metadata_key)
        metadata = json.loads(response['Body'].read().decode('utf-8'))

        # Format response to match frontend expectations
        return jsonify({
            'success': True,
            'modelInfo': {
                'model_type': 'fmu',
                'modelName': metadata.get('modelName', ''),
                'fmiVersion': metadata.get('fmiVersion', ''),
                'description': metadata.get('description', ''),
                'generationTool': metadata.get('generationTool', ''),
            },
            'variables': metadata.get('variables', {})
        }), 200

    except s3_client.exceptions.NoSuchKey:
        return jsonify({"error": f"Metadata not found for: {s3_path}"}), 404
    except Exception as e:
        logger.error(f"Failed to fetch metadata from S3: {e}")
        return jsonify({"error": f"Failed to fetch metadata: {str(e)}"}), 500


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
    # Ensure S3 bucket exists on startup
    ensure_bucket_exists()

    print("=" * 60)
    print(" " * 15 + "SIMULATION API")
    print("=" * 60)
    print(f"S3 Endpoint: {S3_ENDPOINT}")
    print(f"S3 Bucket: {S3_BUCKET}")
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
