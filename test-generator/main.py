"""
Test Generator Service - Generates new test configurations from failed validations

Listens to validation-failure topic and generates N new test payloads with
slightly randomized configurations. Only processes user-initiated failures
to prevent infinite loops.

Flow: validation-failure → Test Generator → simulation topic
"""

from quixstreams import Application
import os
import json
import random
from datetime import datetime, timezone

# for local dev, load env vars from a .env file
from dotenv import load_dotenv
load_dotenv()


def randomize_value(value, use_wide_range: bool = False):
    """Randomize a numeric value by a percentage."""
    if use_wide_range:
        pct = random.uniform(0.10, 0.30)  # 10-30%
    else:
        pct = random.uniform(0.02, 0.20)  # 2-20%
    direction = random.choice([-1, 1])
    new_value = value * (1 + direction * pct)
    # Preserve int type
    if isinstance(value, int):
        return int(round(new_value))
    return new_value


def randomize_config(config: dict) -> dict:
    """
    Randomize numeric values in config, including nested 'parameters' dict.

    Most values get a small change (2-20%), but 1-3 randomly selected
    values use a wider range (10-30%) to explore more diverse solutions.

    The 'success_criteria' is kept unchanged - we want to test against
    the same validation criteria with different simulation parameters.

    Args:
        config: Original configuration dictionary

    Returns:
        dict: New config with randomized numeric values
    """
    new_config = {}

    # Collect all numeric paths for outlier selection
    all_numeric_paths = []
    if 'parameters' in config and isinstance(config['parameters'], dict):
        for k, v in config['parameters'].items():
            if isinstance(v, (int, float)):
                all_numeric_paths.append(('parameters', k))
    for k, v in config.items():
        if k != 'parameters' and k != 'success_criteria' and isinstance(v, (int, float)):
            all_numeric_paths.append((None, k))

    # Select 1-3 paths to use wider range
    num_outliers = min(random.randint(1, 3), len(all_numeric_paths))
    outlier_paths = set(random.sample(all_numeric_paths, num_outliers)) if all_numeric_paths else set()

    for key, value in config.items():
        if key == 'success_criteria':
            # Keep success_criteria unchanged - same validation target
            new_config[key] = value
        elif key == 'parameters' and isinstance(value, dict):
            # Randomize nested parameters
            new_params = {}
            for param_key, param_value in value.items():
                if isinstance(param_value, (int, float)):
                    use_wide = ('parameters', param_key) in outlier_paths
                    new_params[param_key] = randomize_value(param_value, use_wide)
                else:
                    new_params[param_key] = param_value
            new_config[key] = new_params
        elif isinstance(value, (int, float)):
            use_wide = (None, key) in outlier_paths
            new_config[key] = randomize_value(value, use_wide)
        else:
            new_config[key] = value

    return new_config


def generate_test_payloads(row: dict, num_tests: int) -> list:
    """
    Generate N new test payloads from a failed validation.

    Args:
        row: Failed validation payload
        num_tests: Number of test variations to generate

    Returns:
        list: List of new test payloads
    """
    message_key = row.get("message_key", "unknown")
    original_config = row.get("config", {})

    print(f"\n{'='*60}")
    print(f"Generating {num_tests} test variations")
    print(f"  Original key: {message_key}")
    print(f"  Original config: {original_config}")
    print(f"{'='*60}")

    tests = []
    for i in range(num_tests):
        new_config = randomize_config(original_config)

        new_payload = {
            "message_key": f"{message_key}_gen_{i+1}",
            "submitted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "model_filename": row.get("model_filename", ""),  # Keep for display
            "model_s3_path": row.get("model_s3_path", ""),  # S3 path for fetching model
            "input_data": [],  # Clear input_data - simulation will generate new data
            "config": new_config,  # Contains success_criteria for validation
            "source": "system",  # Mark as system-generated to prevent loops
            "parent_key": message_key  # Track lineage
        }
        tests.append(new_payload)

        print(f"  Test {i+1}: {new_config}")

    print(f"{'='*60}\n")
    return tests


def process_failure(row: dict) -> list:
    """
    Process a failed validation message.

    Only generates new tests for user-initiated failures.
    System-generated failures are ignored to prevent infinite loops.

    Args:
        row: Failed validation payload

    Returns:
        list: List of new test payloads (empty if system-generated)
    """
    source = row.get("source", "unknown")
    message_key = row.get("message_key", "unknown")
    validation = row.get("validation", {})

    print(f"\nReceived failure: {message_key}")
    print(f"  Source: {source}")
    print(f"  Validation: {validation.get('reason', 'unknown')}")

    # Only generate new tests for user-initiated failures
    if source != "user":
        print(f"  Skipping - source is '{source}', not 'user'")
        return []

    num_tests = int(os.environ.get("NUM_TESTS", "10"))
    return generate_test_payloads(row, num_tests)


def main():
    """Main entry point for the Test Generator service."""

    num_tests = os.environ.get("NUM_TESTS", "10")

    print("="*60)
    print("Test Generator Service Starting")
    print(f"Tests per failure: {num_tests}")
    print("Only processes user-initiated failures (loop prevention)")
    print("="*60)

    # Setup Quix Streams application
    app = Application(
        consumer_group="test-generator",
        auto_create_topics=True,
        auto_offset_reset="earliest"
    )

    # Get topic names from environment
    input_topic_name = os.environ.get("input", "validation-failure")
    output_topic_name = os.environ.get("output", "simulation")

    print(f"Input topic: {input_topic_name}")
    print(f"Output topic: {output_topic_name}")

    input_topic = app.topic(name=input_topic_name)
    output_topic = app.topic(name=output_topic_name)

    # Get producer for publishing new tests
    producer = app.get_producer()

    # Create streaming dataframe
    sdf = app.dataframe(topic=input_topic)

    # Process each failure and generate new tests
    def handle_failure(row: dict):
        new_tests = process_failure(row)

        # Publish each new test to the simulation topic
        for test in new_tests:
            producer.produce(
                output_topic.name,
                json.dumps(test),
                test["message_key"].encode()
            )
            print(f"Published: {test['message_key']}")

        return row  # Return original for logging

    sdf = sdf.apply(handle_failure)

    # Run the application
    print("Starting Kafka consumer...")
    app.run()


if __name__ == "__main__":
    main()
