"""
FMU Runner - Processes FMU simulation requests from Kafka

Consumes from 'simulation' topic, executes FMU simulation using fmpy,
outputs to 'simulation-results' topic.

FMU files are loaded from the local 'fmu_files' directory.
"""
import os
import logging
from datetime import datetime, timezone

from quixstreams import Application
from dotenv import load_dotenv

from fmu_executor import should_process, run_fmu_simulation

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FMU files directory (local)
FMU_DIR = os.path.join(os.path.dirname(__file__), "fmu_files")


def get_fmu_path(model_filename: str) -> str:
    """
    Get path to FMU file from local directory.

    Args:
        model_filename: Name of the FMU file

    Returns:
        Path to the FMU file on disk

    Raises:
        FileNotFoundError: If FMU file doesn't exist
    """
    fmu_path = os.path.join(FMU_DIR, model_filename)

    if not os.path.exists(fmu_path):
        raise FileNotFoundError(f"FMU file not found: {fmu_path}")

    logger.debug(f"Using FMU: {fmu_path}")
    return fmu_path


def process_message(row: dict) -> dict:
    """
    Process a simulation request message.

    Args:
        row: Kafka message payload

    Returns:
        Result payload with simulation results
    """
    message_key = row.get("message_key", "unknown")
    model_filename = row.get("model_filename", "")

    # Check if this is an FMU file
    if not should_process(model_filename):
        logger.debug(f"Skipping non-FMU file: {model_filename}")
        return None

    logger.info(f"Processing FMU simulation: {message_key}")
    logger.info(f"  Model: {model_filename}")

    started_at = datetime.now(timezone.utc)

    try:
        # Get FMU file path from local directory
        fmu_path = get_fmu_path(model_filename)

        # Extract simulation config
        config = row.get("config", {})
        input_data = row.get("input_data", [])

        # Add start/stop time from config if not present
        if "start_time" not in config:
            config["start_time"] = 0.0
        if "stop_time" not in config:
            config["stop_time"] = 10.0

        # Run simulation
        result = run_fmu_simulation(
            fmu_path=fmu_path,
            input_data=input_data,
            config=config
        )

        completed_at = datetime.now(timezone.utc)
        processing_time_ms = (completed_at - started_at).total_seconds() * 1000

        # Build output payload
        output = {
            "message_key": message_key,
            "submitted_at": row.get("submitted_at", started_at.isoformat().replace("+00:00", "Z")),
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
            "processing_time_ms": processing_time_ms,
            "model_filename": model_filename,
            "config": config,
            "status": result["status"],
            "error_message": result.get("error_message"),
            "input_data": result["input_data"],
        }

        logger.info(f"Completed FMU simulation: {message_key}")
        logger.info(f"  Status: {result['status']}")
        logger.info(f"  Processing time: {processing_time_ms:.1f}ms")
        logger.info(f"  Output rows: {len(result['input_data'])}")

        return output

    except Exception as e:
        logger.error(f"FMU simulation failed: {e}")
        completed_at = datetime.now(timezone.utc)
        processing_time_ms = (completed_at - started_at).total_seconds() * 1000

        return {
            "message_key": message_key,
            "submitted_at": row.get("submitted_at", started_at.isoformat().replace("+00:00", "Z")),
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
            "processing_time_ms": processing_time_ms,
            "model_filename": model_filename,
            "config": row.get("config", {}),
            "status": "error",
            "error_message": str(e),
            "input_data": [],
        }


def main():
    """Main entry point for the FMU Runner service."""
    logger.info("=" * 60)
    logger.info("FMU Runner Service Starting")
    logger.info(f"  FMU directory: {FMU_DIR}")
    logger.info("=" * 60)

    # Ensure FMU directory exists
    os.makedirs(FMU_DIR, exist_ok=True)

    # Setup Quix Streams application
    app = Application(
        consumer_group=os.getenv("CONSUMER_GROUP", "fmu-runner"),
        auto_create_topics=True,
        auto_offset_reset=os.getenv("AUTO_OFFSET_RESET", "earliest")
    )

    # Get topic names from environment
    input_topic_name = os.environ.get("input", "simulation")
    output_topic_name = os.environ.get("output", "simulation-results")

    logger.info(f"Input topic: {input_topic_name}")
    logger.info(f"Output topic: {output_topic_name}")

    input_topic = app.topic(name=input_topic_name)
    output_topic = app.topic(name=output_topic_name)

    # Create streaming dataframe
    sdf = app.dataframe(topic=input_topic)

    # Filter to only process FMU files
    sdf = sdf.filter(lambda row: should_process(row.get("model_filename", "")))

    # Process each message
    sdf = sdf.apply(process_message)

    # Filter out None results
    sdf = sdf.filter(lambda row: row is not None)

    # Write to output topic
    sdf.to_topic(output_topic)

    # Run the application
    logger.info("Starting Kafka consumer...")
    app.run()


if __name__ == "__main__":
    main()
