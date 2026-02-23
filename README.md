# FMU Runner

A simple FMU (Functional Mock-up Unit) simulation runner using Kafka/Quix Streams.

## About This Example

This is a **simplified example** designed to demonstrate the core concept of running FMU simulations via a streaming pipeline. It uses static FMU files stored locally within the service.

### Production Considerations

In a real-world implementation, you would typically:

**FMU Storage**
- Store FMU files in blob storage (S3, Azure Blob, MinIO) rather than bundling them with the service
- Reference models by URL or storage path in simulation requests
- Support dynamic model uploads and versioning

**Downstream Processing**
- Add processing stages to analyse simulation results (validation, aggregation, anomaly detection)
- Use sinks to persist results to databases, data lakes, or time-series stores for later analysis
- Implement feedback loops for parameter optimization or automated testing

**Example Production Architecture**
```
API/Source → [simulation] → FMU Runner → [results] → Validator → [validated] → Data Lake Sink
                                ↑                         ↓
                           Blob Storage            Parameter Optimizer
```

## Architecture

```
Test Source → [simulation] → FMU Runner → [simulation-results]
```

- **Test Source**: Publishes simulation requests to the `simulation` topic
- **FMU Runner**: Executes FMU simulations using fmpy and publishes results

## Setup

1. Place your FMU file in `fmu-runner/fmu_files/` (e.g., `BouncingBall.fmu`)
2. Configure `MODEL_FILENAME` in test-source to match your FMU file

## Message Format

### Input (simulation topic)

```json
{
  "message_key": "2024-02-23T12:30:00_BouncingBall.fmu",
  "submitted_at": "2024-02-23T12:30:00Z",
  "model_filename": "BouncingBall.fmu",
  "config": {
    "start_time": 0,
    "stop_time": 10,
    "parameters": {}
  },
  "input_data": []
}
```

### Output (simulation-results topic)

```json
{
  "message_key": "2024-02-23T12:30:00_BouncingBall.fmu",
  "status": "success",
  "processing_time_ms": 150,
  "input_data": [...]
}
```

## Topics

| Topic | Description |
|-------|-------------|
| `simulation` | Simulation requests |
| `simulation-results` | Simulation output data |
