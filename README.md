# FMU Simulation Feedback Loop

An automated parameter optimization system for FMU (Functional Mock-up Unit) simulations. Upload an FMU model with success criteria, and the system will automatically explore parameter variations to find configurations that meet your targets.

## How It Works

1. **Submit** - Upload an FMU file with a JSON config specifying parameters and success criteria
2. **Simulate** - The FMU runner executes the simulation using fmpy
3. **Validate** - The validator checks if the output meets your success criteria (e.g., `max(h) >= 10`)
4. **Optimize** - If validation fails, the test generator creates parameter variations and resubmits them
5. **Converge** - The system finds configurations that satisfy your criteria

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   HTTP API  │────▶│  FMU Runner │────▶│  Validator  │
│  (Frontend) │     │   (fmpy)    │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌─────────────┐             │
                    │    Test     │◀────────────┘
                    │  Generator  │   (on failure)
                    └─────────────┘
```

### Services

| Service | Purpose |
|---------|---------|
| **HTTP API** | Web frontend for uploading FMUs and viewing results |
| **FMU Runner** | Executes FMU simulations using fmpy |
| **Validator** | Checks if simulation output meets success criteria |
| **Test Generator** | Creates parameter variations when validation fails |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| **Redpanda** | Kafka-compatible message broker |
| **MinIO** | S3-compatible object storage for results |

## Configuration Format

```json
{
  "start_time": 0,
  "stop_time": 10,
  "parameters": {
    "g": -9.81,
    "e": 0.7
  },
  "success_criteria": {
    "field_name": "h",
    "target_value": 1.0
  }
}
```

- **start_time / stop_time**: Simulation time range
- **parameters**: FMU parameter overrides (optional)
- **success_criteria**: Validation rule - `max(field_name) >= target_value`

## Local Development

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development)

### Running Locally

```bash
docker-compose -f docker-compose.local.yml up --build
```

Access the frontend at http://localhost:80

### Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `HTTP_AUTH_TOKEN` | All | Bearer token for API authentication |
| `Quix__Broker__Address` | All | Kafka broker address |

## Quix Cloud Deployment

This project is designed to run on [Quix Cloud](https://quix.io). See [SETUP.md](SETUP.md) for deployment instructions.

### Syncing

After cloning the template, sync to deploy all services:

1. Press the **Sync** button in the Quix UI
2. Configure required secrets when prompted
3. Wait for all services to start (may take a few restart cycles)

## Example: BouncingBall FMU

The classic BouncingBall FMU simulates a ball dropped from a height:

- **Outputs**: `h` (height), `v` (velocity)
- **Parameters**: `g` (gravity), `e` (restitution coefficient)

Example config to find parameters where max height reaches 1.5m:

```json
{
  "start_time": 0,
  "stop_time": 10,
  "parameters": {
    "g": -9.81,
    "e": 0.7
  },
  "success_criteria": {
    "field_name": "h",
    "target_value": 1.5
  }
}
```

## Topics

| Topic | Description |
|-------|-------------|
| `simulation` | Incoming simulation requests |
| `simulation-results` | Raw simulation output data |
| `validation-success` | Runs that passed validation |
| `validation-failure` | Runs that failed validation |
