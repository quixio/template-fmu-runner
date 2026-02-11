"""
Test script to verify the flatten_for_results function works correctly.
Run with: python test_flatten.py
"""
import json
import csv
from pathlib import Path
from datetime import datetime


# Copy of functions from main.py (to avoid importing QuixLakeSink dependencies)
def flatten_for_results(row: dict) -> dict:
    """
    Flatten the incoming message for the results table.
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
        params = config.get('parameters', config)
        if isinstance(params, dict):
            for key, value in params.items():
                if not isinstance(value, (dict, list)):
                    result[f'config_{key}'] = value

    # Add ts_ms for timestamp-based partitioning
    ts_source = result.get('validation_validated_at') or result.get('completed_at')
    if ts_source:
        try:
            ts_str = ts_source.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts_str)
            result['ts_ms'] = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            result['ts_ms'] = int(datetime.now().timestamp() * 1000)
    else:
        result['ts_ms'] = int(datetime.now().timestamp() * 1000)

    return result


def has_validation_result(row: dict) -> bool:
    """Check if the message contains a validation result."""
    validation = row.get('validation', {})
    return bool(validation and 'passed' in validation)


def has_timeseries_data(row: dict) -> bool:
    """Check if the message contains timeseries data."""
    input_data = row.get('input_data', [])
    return bool(input_data and len(input_data) > 0)


def explode_timeseries(row: dict) -> list:
    """Explode the input_data array into individual timeseries rows."""
    message_key = row.get('message_key', 'unknown')
    input_data = row.get('input_data', [])
    submitted_at = row.get('submitted_at', '')

    # Parse base timestamp
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
        ts_row = {'message_key': message_key}

        for key, value in point.items():
            if not isinstance(value, (dict, list)):
                ts_row[key] = value

        time_val = point.get('time', 0)
        if isinstance(time_val, (int, float)):
            ts_row['ts_ms'] = base_ts_ms + int(time_val * 1000)
        else:
            ts_row['ts_ms'] = base_ts_ms

        rows.append(ts_row)

    return rows


def load_example(filename: str) -> dict:
    """Load an example JSON file."""
    path = Path(__file__).parent / "examples" / filename
    with open(path) as f:
        return json.load(f)


def test_flatten():
    """Test flattening both pass and fail examples."""
    print("=" * 60)
    print("Testing flatten_for_results()")
    print("=" * 60)

    examples = [
        ("input_message.json", "FAIL case"),
        ("input_message_pass.json", "PASS case"),
    ]

    results = []
    for filename, description in examples:
        print(f"\n{description}: {filename}")
        print("-" * 40)

        # Load input
        input_data = load_example(filename)
        print(f"Input keys: {list(input_data.keys())}")
        print(f"Has validation: {has_validation_result(input_data)}")

        # Flatten
        flattened = flatten_for_results(input_data)
        results.append(flattened)

        # Show result
        print(f"Output keys ({len(flattened)}): {list(flattened.keys())}")
        print(f"\nFlattened values:")
        for key, value in sorted(flattened.items()):
            print(f"  {key}: {value}")

    # Write results to CSV for comparison
    output_path = Path(__file__).parent / "examples" / "test_output_results.csv"
    if results:
        fieldnames = list(results[0].keys())
        # Ensure all fieldnames from all results are included
        for r in results[1:]:
            for key in r.keys():
                if key not in fieldnames:
                    fieldnames.append(key)

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n{'=' * 60}")
        print(f"Results written to: {output_path}")
        print("Compare with: examples/expected_results_table_multi.csv")

    return results


def test_filter():
    """Test the has_validation_result filter."""
    print("\n" + "=" * 60)
    print("Testing has_validation_result()")
    print("=" * 60)

    test_cases = [
        ({"validation": {"passed": True}}, True, "has validation.passed=True"),
        ({"validation": {"passed": False}}, True, "has validation.passed=False"),
        ({"validation": {}}, False, "empty validation object"),
        ({}, False, "no validation key"),
        ({"other": "data"}, False, "other data only"),
    ]

    all_passed = True
    for data, expected, description in test_cases:
        result = has_validation_result(data)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            all_passed = False
        print(f"  [{status}] {description}: {result} (expected {expected})")

    return all_passed


def test_timeseries_explode():
    """Test exploding timeseries data."""
    print("\n" + "=" * 60)
    print("Testing explode_timeseries()")
    print("=" * 60)

    # Load example with timeseries data
    input_data = load_example("input_message.json")
    print(f"Input has {len(input_data.get('input_data', []))} data points")
    print(f"Has timeseries: {has_timeseries_data(input_data)}")

    # Explode
    rows = explode_timeseries(input_data)
    print(f"Exploded into {len(rows)} rows")

    if rows:
        print(f"\nColumns: {list(rows[0].keys())}")
        print(f"\nFirst 3 rows:")
        for i, row in enumerate(rows[:3]):
            print(f"  {i}: {row}")

    # Write to CSV
    output_path = Path(__file__).parent / "examples" / "test_output_timeseries.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nTimeseries written to: {output_path}")

    return rows


def test_timeseries_filter():
    """Test the has_timeseries_data filter."""
    print("\n" + "=" * 60)
    print("Testing has_timeseries_data()")
    print("=" * 60)

    test_cases = [
        ({"input_data": [{"time": 0, "value": 1}]}, True, "has input_data with 1 point"),
        ({"input_data": []}, False, "empty input_data array"),
        ({}, False, "no input_data key"),
        ({"input_data": None}, False, "input_data is None"),
    ]

    all_passed = True
    for data, expected, description in test_cases:
        result = has_timeseries_data(data)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            all_passed = False
        print(f"  [{status}] {description}: {result} (expected {expected})")

    return all_passed


if __name__ == "__main__":
    test_flatten()
    filter_ok = test_filter()
    test_timeseries_explode()
    ts_filter_ok = test_timeseries_filter()

    print("\n" + "=" * 60)
    if filter_ok and ts_filter_ok:
        print("All tests passed!")
    else:
        print("Some tests failed!")
    print("=" * 60)
