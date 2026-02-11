"""
Background Kafka consumer for local development.

Consumes validation results from Kafka topics and stores them in the LocalStore
for querying by the API endpoints.

Uses QuixStreams' consumer directly (without app.run()) to avoid signal handler
issues in background threads.
"""
import json
import logging
import threading
import os
from typing import TYPE_CHECKING

from quixstreams import Application

if TYPE_CHECKING:
    from local_store import LocalStore

logger = logging.getLogger(__name__)


def start_background_consumer(store: "LocalStore"):
    """
    Start a background thread that consumes validation results from Kafka.

    Args:
        store: LocalStore instance to store results in
    """
    def consume():
        logger.info("LocalStore consumer: starting background Kafka consumer")

        try:
            # Create QuixStreams Application
            app = Application(
                consumer_group="http-api-local-store",
                auto_create_topics=False,
                auto_offset_reset="earliest"
            )

            # Get topic names from environment
            success_topic_name = os.environ.get("validation_success_topic", "validation-success")
            failure_topic_name = os.environ.get("validation_failure_topic", "validation-failure")

            logger.info(f"LocalStore consumer: subscribing to {success_topic_name}, {failure_topic_name}")

            # Get the low-level consumer from QuixStreams
            consumer = app.get_consumer()
            consumer.subscribe([success_topic_name, failure_topic_name])

            logger.info("LocalStore consumer: starting consume loop")

            while True:
                try:
                    msg = consumer.poll(timeout=1.0)

                    if msg is None:
                        continue

                    if msg.error():
                        logger.error(f"LocalStore consumer: Kafka error: {msg.error()}")
                        continue

                    # Parse the message
                    try:
                        value = json.loads(msg.value().decode('utf-8'))
                        message_key = value.get("message_key", "unknown")
                        validation = value.get("validation", {})
                        passed = validation.get("passed", False)

                        logger.info(f"LocalStore consumer: received {message_key} "
                                   f"({'PASS' if passed else 'FAIL'}) from {msg.topic()}")

                        # Store the result
                        store.add_result(message_key, value)

                        # Commit offset
                        consumer.commit(msg)

                    except json.JSONDecodeError as e:
                        logger.error(f"LocalStore consumer: failed to parse message: {e}")

                except Exception as e:
                    logger.error(f"LocalStore consumer: error processing message: {e}")

        except Exception as e:
            logger.error(f"LocalStore consumer: error in background consumer: {e}", exc_info=True)

    # Start the consumer in a daemon thread
    # Daemon threads are automatically killed when the main program exits
    thread = threading.Thread(target=consume, name="LocalStoreConsumer", daemon=True)
    thread.start()

    logger.info("LocalStore consumer: background thread started")
    return thread
