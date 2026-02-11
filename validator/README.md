# Validator

Validates simulation results against threshold and routes to success or failure topics.

## Overview

This service:
1. Reads simulation results from the `simulation-results` Kafka topic
2. Calculates the maximum height from the bouncing ball position data
3. Compares against the threshold value from the original request
4. Routes to `validation-success` or `validation-failure` topic based on result

## Validation Logic

```
max(position) >= threshold → SUCCESS
max(position) < threshold  → FAILURE
```

## Input Payload Format

The service expects simulation results from the Simulink Runner:

```json
{
  "message_key": "2024-02-02T12:30:00_model.whl",
  "submitted_at": "2024-02-02T12:30:00Z",
  "started_at": "2024-02-02T12:30:01Z",
  "completed_at": "2024-02-02T12:30:15Z",
  "processing_time_ms": 14000,
  "config": {
    "g_acc": -9.8,
    "init_vel": 15,
    "init_pos": 2,
    "k_rest": -0.75
  },
  "threshold": 10.0,
  "status": "completed",
  "input_data": [
    {"time": 0, "position": 2, "velocity": 15},
    {"time": 0.01, "position": 2.15, "velocity": 14.9},
    ...
  ]
}
```

## Output Format

The output includes all original fields plus validation results:

```json
{
  "message_key": "2024-02-02T12:30:00_model.whl",
  "submitted_at": "2024-02-02T12:30:00Z",
  "started_at": "2024-02-02T12:30:01Z",
  "completed_at": "2024-02-02T12:30:15Z",
  "processing_time_ms": 14000,
  "config": {...},
  "threshold": 10.0,
  "status": "completed",
  "input_data": [...],
  "validation": {
    "metric": "max_height",
    "calculated_value": 13.48,
    "threshold": 10.0,
    "passed": true,
    "reason": "Max height 13.48m meets threshold 10m",
    "validated_at": "2024-02-02T12:30:16Z"
  }
}
```

## Topic Routing

- **validation-success**: Messages where `max(position) >= threshold`
- **validation-failure**: Messages where `max(position) < threshold`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `input` | Kafka topic for simulation results | `simulation-results` |
| `output_success` | Kafka topic for successful validations | `validation-success` |
| `output_failure` | Kafka topic for failed validations | `validation-failure` |

## Docker Build

```bash
docker build -t validator .
```

## Local Testing

With the full stack running:

1. Submit a simulation with threshold = 10 (should PASS, max height ~13.5m)
2. Submit a simulation with threshold = 15 (should FAIL, max height ~13.5m)

Check logs:
```bash
docker logs validator -f
```
