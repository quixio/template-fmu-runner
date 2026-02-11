"""
Validator Service - Validates FMU simulation results against success criteria

Consumes from simulation-results topic and validates outputs against
the success_criteria defined in the config.

Validation: max(field_name) >= target_value

Routes validated messages to success or failure topics.
"""

from quixstreams import Application
import os
from datetime import datetime, timezone
from typing import Dict, List, Any

# for local dev, load env vars from a .env file
from dotenv import load_dotenv
load_dotenv()


def validate_simulation(row: dict) -> dict:
    """
    Validate simulation results using success_criteria from config.

    The config should contain:
    {
        "success_criteria": {
            "field_name": "h",      # Output field to validate
            "target_value": 1.0     # Threshold (max >= target)
        }
    }

    Args:
        row: Simulation result payload containing input_data and config

    Returns:
        dict: Original payload enriched with validation results
    """
    input_data = row.get("input_data", [])
    message_key = row.get("message_key", "unknown")
    config = row.get("config", {})
    success_criteria = config.get("success_criteria", {})

    # Extract validation parameters
    field_name = success_criteria.get("field_name", "position")
    target_value = success_criteria.get("target_value", 0)

    print(f"\n{'='*60}")
    print(f"Validating: {message_key}")
    print(f"  Data points: {len(input_data)}")
    print(f"  Criteria: max({field_name}) >= {target_value}")

    # Extract values for the specified field
    values = [point.get(field_name) for point in input_data if field_name in point]

    if not values:
        result = {
            "metric": f"max_{field_name}",
            "calculated_value": None,
            "target_value": target_value,
            "passed": False,
            "reason": f"No '{field_name}' data in simulation results"
        }
    else:
        # Convert to numeric and find max
        try:
            numeric_values = [float(v) for v in values if v is not None]
            if not numeric_values:
                result = {
                    "metric": f"max_{field_name}",
                    "calculated_value": None,
                    "target_value": target_value,
                    "passed": False,
                    "reason": f"No numeric values for '{field_name}'"
                }
            else:
                calculated = max(numeric_values)
                passed = calculated >= float(target_value)

                result = {
                    "metric": f"max_{field_name}",
                    "calculated_value": calculated,
                    "target_value": target_value,
                    "passed": passed,
                    "reason": f"max({field_name})={calculated:.4f} {'meets' if passed else 'below'} target {target_value}"
                }
        except (ValueError, TypeError) as e:
            result = {
                "metric": f"max_{field_name}",
                "calculated_value": None,
                "target_value": target_value,
                "passed": False,
                "reason": f"Error converting values to numeric: {e}"
            }

    print(f"  Result: {'PASS' if result['passed'] else 'FAIL'} - {result['reason']}")
    print(f"{'='*60}")

    # Add validation results to payload
    row["validation"] = {
        **result,
        "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    return row


def main():
    """Main entry point for the Validator service."""

    print("="*60)
    print("Validator Service Starting")
    print("Validation: max(field_name) >= target_value")
    print("  (from config.success_criteria)")
    print("="*60)

    # Setup Quix Streams application
    app = Application(
        consumer_group="validator",
        auto_create_topics=True,
        auto_offset_reset="earliest"
    )

    # Get topic names from environment
    input_topic_name = os.environ.get("input", "simulation-results")
    success_topic_name = os.environ.get("output_success", "validation-success")
    failure_topic_name = os.environ.get("output_failure", "validation-failure")

    print(f"Input topic: {input_topic_name}")
    print(f"Success topic: {success_topic_name}")
    print(f"Failure topic: {failure_topic_name}")

    input_topic = app.topic(name=input_topic_name)
    success_topic = app.topic(name=success_topic_name)
    failure_topic = app.topic(name=failure_topic_name)

    # Create streaming dataframe
    sdf = app.dataframe(topic=input_topic)

    # Validate each message
    sdf = sdf.apply(validate_simulation)

    # Split stream based on validation result
    success_sdf = sdf.filter(lambda row: row.get("validation", {}).get("passed", False))
    failure_sdf = sdf.filter(lambda row: not row.get("validation", {}).get("passed", True))

    # Write to respective topics
    success_sdf.to_topic(success_topic)
    failure_sdf.to_topic(failure_topic)

    # Run the application
    print("Starting Kafka consumer...")
    app.run()


if __name__ == "__main__":
    main()
