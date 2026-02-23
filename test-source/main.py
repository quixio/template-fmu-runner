"""
Test Source - Generates sample simulation requests for FMU Runner

Publishes simulation requests to the 'simulation' topic.
"""
import os
import json
import logging
from datetime import datetime, timezone

from quixstreams import Application
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_simulation_request(model_filename: str, config: dict = None) -> dict:
    """
    Create a simulation request message.

    Args:
        model_filename: Name of the FMU file (must exist in fmu-runner/fmu_files/)
        config: Optional simulation configuration

    Returns:
        Simulation request payload
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

    if config is None:
        config = {
            "start_time": 0.0,
            "stop_time": 10.0,
            "parameters": {}
        }

    return {
        "message_key": f"{timestamp}_{model_filename}",
        "submitted_at": now.isoformat().replace("+00:00", "Z"),
        "model_filename": model_filename,
        "config": config,
        "input_data": []
    }


def main():
    """Main entry point for the Test Source service."""
    logger.info("=" * 60)
    logger.info("Test Source Starting")
    logger.info("=" * 60)

    # Setup Quix Streams application
    app = Application(
        consumer_group=os.getenv("CONSUMER_GROUP", "test-source"),
        auto_create_topics=True
    )

    # Get topic name from environment
    output_topic_name = os.environ.get("output", "simulation")
    logger.info(f"Output topic: {output_topic_name}")

    # Get configuration
    model_filename = os.environ.get("MODEL_FILENAME", "BouncingBall.fmu")
    logger.info(f"Model filename: {model_filename}")

    # Create producer and send single request
    with app.get_producer() as producer:
        topic = app.topic(name=output_topic_name)

        # Create simulation request
        request = create_simulation_request(model_filename)
        message_key = request["message_key"]

        logger.info(f"Sending simulation request: {message_key}")

        # Serialize and send
        producer.produce(
            topic=topic.name,
            key=message_key.encode(),
            value=request
        )
        producer.flush()

        logger.info(f"Sent successfully")

    logger.info("Done")


if __name__ == "__main__":
    main()
