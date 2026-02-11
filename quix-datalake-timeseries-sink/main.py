"""
Quix TS Datalake Sink - Main Entry Point

This application consumes data from a Kafka topic and writes it to S3 as
Hive-partitioned Parquet files with optional Iceberg catalog registration.

Data is split into two tables:
- results: Flattened validation results (one row per simulation)
- timeseries: Raw time series data points (one row per data point)
"""
import os
import logging
from datetime import datetime

from quixstreams import Application
from quixlake_sink import QuixLakeSink

# Configure logging
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def flatten_for_results(row: dict) -> dict:
    """
    Flatten the incoming message for the results table.

    - Flattens the 'validation' nested object (validation.passed -> validation_passed)
    - Flattens the 'config' nested object (config.key -> config_key)
    - Removes 'input_data' array (stored separately in timeseries table)
    - Adds a timestamp for partitioning

    Args:
        row: Original message with nested structure

    Returns:
        dict: Flattened row suitable for results table
    """
    result = {}

    # Copy top-level scalar fields (excluding nested objects and arrays)
    skip_fields = {'validation', 'config', 'input_data', 'model_data'}
    for key, value in row.items():
        if key in skip_fields:
            continue
        if not isinstance(value, (dict, list)):
            result[key] = value

    # Flatten validation object
    validation = row.get('validation', {})
    if validation:
        for key, value in validation.items():
            result[f'validation_{key}'] = value

    # Flatten config object (prefix with config_)
    config = row.get('config', {})
    if config and isinstance(config, dict):
        # Handle nested parameters within config
        params = config.get('parameters', config)
        if isinstance(params, dict):
            for key, value in params.items():
                # Only include scalar values
                if not isinstance(value, (dict, list)):
                    result[f'config_{key}'] = value

    # Add ts_ms for timestamp-based partitioning (convert ISO to milliseconds)
    ts_source = result.get('validation_validated_at') or result.get('completed_at')
    if ts_source:
        try:
            # Parse ISO format (handles both Z and +00:00 suffixes)
            ts_str = ts_source.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts_str)
            result['ts_ms'] = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            # If parsing fails, use current time
            result['ts_ms'] = int(datetime.now().timestamp() * 1000)
    else:
        result['ts_ms'] = int(datetime.now().timestamp() * 1000)

    return result


def has_validation_result(row: dict) -> bool:
    """
    Check if the message contains a validation result.

    Args:
        row: Message to check

    Returns:
        bool: True if message has validation data with a passed field
    """
    validation = row.get('validation', {})
    return bool(validation and 'passed' in validation)


def has_timeseries_data(row: dict) -> bool:
    """
    Check if the message contains timeseries data.

    Args:
        row: Message to check

    Returns:
        bool: True if message has input_data array with at least one point
    """
    input_data = row.get('input_data', [])
    return bool(input_data and len(input_data) > 0)


def explode_timeseries(row: dict) -> list:
    """
    Explode the input_data array into individual timeseries rows.

    Each data point in input_data becomes a separate row with:
    - message_key: Reference to parent simulation
    - model_filename: Reference to model (for partitioning)
    - All fields from the data point (time, position, velocity, etc.)
    - ts_ms: Timestamp in milliseconds for partitioning

    Args:
        row: Original message with input_data array

    Returns:
        list: List of flattened timeseries rows
    """
    message_key = row.get('message_key', 'unknown')
    model_filename = row.get('model_filename', 'unknown')
    input_data = row.get('input_data', [])
    submitted_at = row.get('submitted_at', '')

    # Parse base timestamp for calculating ts_ms
    base_ts_ms = None
    if submitted_at:
        try:
            ts_str = submitted_at.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts_str)
            base_ts_ms = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            base_ts_ms = int(datetime.now().timestamp() * 1000)
    else:
        base_ts_ms = int(datetime.now().timestamp() * 1000)

    rows = []
    for point in input_data:
        ts_row = {
            'message_key': message_key,
            'model_filename': model_filename,
        }

        # Copy all fields from the data point
        for key, value in point.items():
            # Only include scalar values
            if not isinstance(value, (dict, list)):
                # Ensure numeric fields are consistently typed
                if key == 'time':
                    try:
                        ts_row[key] = float(value)
                    except (ValueError, TypeError):
                        ts_row[key] = 0.0
                else:
                    ts_row[key] = value

        # Calculate ts_ms based on time field if available
        time_val = ts_row.get('time', 0.0)
        # Add time offset (assuming time is in seconds) to base timestamp
        ts_row['ts_ms'] = base_ts_ms + int(time_val * 1000)

        rows.append(ts_row)

    return rows


def parse_comma_list(value: str) -> list:
    """
    Parse a comma-separated list of values.

    Args:
        value: Comma-separated string (e.g., "topic1,topic2" or "year,month,day")

    Returns:
        List of values, or empty list if input is empty
    """
    if not value or value.strip() == "":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


# Initialize Quix Streams Application
app = Application(
    consumer_group=os.getenv("CONSUMER_GROUP", "s3_direct_sink_v1.0"),
    auto_offset_reset=os.getenv("AUTO_OFFSET_RESET", "latest"),
    commit_interval=int(os.getenv("COMMIT_INTERVAL", "30"))
)

# Parse configuration
hive_columns = parse_comma_list(os.getenv("HIVE_COLUMNS", ""))
auto_discover = os.getenv("AUTO_DISCOVER", "true").lower() == "true"

# Build list of input topics from environment variables
input_topics = []
if os.environ.get("input"):
    input_topics.append(os.environ["input"])
if os.environ.get("input_success"):
    input_topics.append(os.environ["input_success"])

# Common S3 configuration
s3_config = {
    "s3_bucket": os.environ["S3_BUCKET"],
    "s3_prefix": os.getenv("S3_PREFIX", "data"),
    "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
    "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    "aws_region": os.getenv("AWS_REGION", "us-east-1"),
    "s3_endpoint_url": os.getenv("AWS_ENDPOINT_URL"),
    "catalog_url": os.getenv("CATALOG_URL"),
    "catalog_auth_token": os.getenv("CATALOG_AUTH_TOKEN"),
    "auto_discover": auto_discover,
    "namespace": os.getenv("CATALOG_NAMESPACE", "default"),
    "auto_create_bucket": True,
    "max_workers": int(os.getenv("MAX_WRITE_WORKERS", "10")),
}

# Results table sink - stores flattened validation results
results_sink = QuixLakeSink(
    **s3_config,
    table_name="results",
    hive_columns=hive_columns,
    timestamp_column=os.getenv("TIMESTAMP_COLUMN", "ts_ms"),
)

# Timeseries table sink - stores exploded time series data points
timeseries_sink = QuixLakeSink(
    **s3_config,
    table_name="timeseries",
    hive_columns=hive_columns,
    timestamp_column=os.getenv("TIMESTAMP_COLUMN", "ts_ms"),
)

# Process each input topic
for topic_name in input_topics:
    # Create streaming dataframe for this topic
    sdf = app.dataframe(topic=app.topic(topic_name))

    # Filter for messages with validation results, flatten, and sink to results table
    results_sdf = sdf.filter(has_validation_result)
    results_sdf = results_sdf.apply(flatten_for_results)
    results_sdf.sink(results_sink)

    # Filter for messages with timeseries data, explode, and sink to timeseries table
    timeseries_sdf = sdf.filter(has_timeseries_data)
    timeseries_sdf = timeseries_sdf.apply(explode_timeseries, expand=True)
    timeseries_sdf.sink(timeseries_sink)

logger.info("Starting Quix TS Datalake Sink")
logger.info(f"  Input topics: {input_topics}")
logger.info(f"  Results table: s3://{os.environ['S3_BUCKET']}/{os.getenv('S3_PREFIX', 'data')}/results")
logger.info(f"  Timeseries table: s3://{os.environ['S3_BUCKET']}/{os.getenv('S3_PREFIX', 'data')}/timeseries")
logger.info(f"  Partitioning: {hive_columns if hive_columns else 'none'}")

if __name__ == "__main__":
    app.run()
