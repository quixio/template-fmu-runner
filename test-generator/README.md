# Test Generator

Generates new test configurations from failed validations to automatically search for passing parameters.

## Overview

This service:
1. Reads failed validations from the `validation-failure` Kafka topic
2. Generates N new test payloads with slightly randomized configurations
3. Publishes new tests to the `simulation` topic for re-processing
4. Only processes user-initiated failures to prevent infinite loops

## Loop Prevention

The service uses the `source` field to prevent infinite loops:
- `source: "user"` → Generate new tests
- `source: "system"` → Ignore (already a generated test)

## Randomization Logic

Each numeric config value is independently randomized by ±2-10%:

```
Original: {"g_acc": -9.8, "init_vel": 15, "init_pos": 2, "k_rest": -0.75}

Generated variations:
  Test 1: {"g_acc": -10.5, "init_vel": 16.2, "init_pos": 1.85, "k_rest": -0.69}
  Test 2: {"g_acc": -9.2, "init_vel": 13.8, "init_pos": 2.15, "k_rest": -0.81}
  ...
```

## Input Payload Format

Expects failed validation messages:

```json
{
  "message_key": "2024-02-02T12:30:00_model.whl",
  "model": {"filename": "model.whl"},
  "config": {"g_acc": -9.8, "init_vel": 15, "init_pos": 2, "k_rest": -0.75},
  "threshold": 15.0,
  "source": "user",
  "validation": {
    "metric": "max_height",
    "calculated_value": 13.48,
    "threshold": 15.0,
    "passed": false,
    "reason": "Max height 13.48m below threshold 15m"
  }
}
```

## Output Payload Format

Generates new simulation requests:

```json
{
  "message_key": "2024-02-02T12:30:00_model.whl_gen_1",
  "submitted_at": "2024-02-02T12:31:00Z",
  "model": {"filename": "model.whl"},
  "input_data": [],
  "config": {"g_acc": -10.5, "init_vel": 16.2, "init_pos": 1.85, "k_rest": -0.69},
  "threshold": 15.0,
  "source": "system",
  "parent_key": "2024-02-02T12:30:00_model.whl"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `input` | Kafka topic for failed validations | `validation-failure` |
| `output` | Kafka topic for new test requests | `simulation` |
| `NUM_TESTS` | Number of test variations per failure | `10` |

## Message Flow

```
User submits (source: "user")
    ↓
Simulation Runner → Validator → FAIL
    ↓
validation-failure topic
    ↓
Test Generator (source == "user" ✓)
    ↓
Generates 10 new payloads (source: "system")
    ↓
simulation topic
    ↓
Simulation Runner → Validator
    ↓
PASS → validation-success ✓
FAIL → validation-failure → Test Generator (source == "system" ✗ SKIP)
```

## Docker Build

```bash
docker build -t test-generator .
```

## Local Testing

1. Submit a simulation that will fail (threshold higher than max height)
2. Watch the test generator create variations:
   ```bash
   docker logs test-generator -f
   ```
3. Watch the validator process the generated tests:
   ```bash
   docker logs validator -f
   ```
