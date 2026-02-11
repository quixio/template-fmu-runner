# Simulink Feedback Loop Architecture

## System Overview

```mermaid
flowchart TB
    subgraph Frontend["Simulation Frontend (Svelte)"]
        UI[Web UI<br/>Port 3000]
    end

    subgraph API["HTTP API Source (Flask)"]
        POST[POST /simulation]
        GET[GET /models/filename]
        STORE[(state/models/)]
    end

    subgraph Kafka["RedPanda / Kafka"]
        SIM_TOPIC[simulation<br/>Bronze]
        RESULTS_TOPIC[simulation-results<br/>Silver]
        SUCCESS_TOPIC[validation-success<br/>Gold]
        FAILURE_TOPIC[validation-failure<br/>Silver]
    end

    subgraph Runner["Simulink Runner"]
        CONSUME_SIM[Consume simulation]
        FETCH_MODEL[Fetch model from API]
        RUN_SIM[Execute MATLAB/Simulink]
        WHEEL_CACHE[(state/wheels/)]
    end

    subgraph Validator["Validator Service"]
        VALIDATE[Check threshold]
        ROUTE{max_height >= threshold?}
    end

    subgraph TestGen["Test Generator"]
        CHECK_SOURCE{source == user?}
        RANDOMIZE[Randomize config ±2-20%<br/>1-3 outliers ±10-30%]
    end

    %% Frontend to API
    UI -->|"HTTP POST<br/>model.data (base64)<br/>input_data, config, threshold"| POST

    %% API stores model and publishes reference
    POST -->|"Store binary"| STORE
    POST -->|"Publish reference only<br/>{filename, input_data, config, threshold}"| SIM_TOPIC

    %% Simulink Runner flow
    SIM_TOPIC --> CONSUME_SIM
    CONSUME_SIM -->|"model.filename"| FETCH_MODEL
    FETCH_MODEL -->|"GET /models/filename"| GET
    GET -->|"Binary"| STORE
    FETCH_MODEL --> RUN_SIM
    RUN_SIM -->|"Cache wheel"| WHEEL_CACHE
    RUN_SIM -->|"Results + enriched input_data"| RESULTS_TOPIC

    %% Validator flow
    RESULTS_TOPIC --> VALIDATE
    VALIDATE --> ROUTE
    ROUTE -->|"Yes (passed)"| SUCCESS_TOPIC
    ROUTE -->|"No (failed)"| FAILURE_TOPIC

    %% Test Generator feedback loop
    FAILURE_TOPIC --> CHECK_SOURCE
    CHECK_SOURCE -->|"Yes"| RANDOMIZE
    CHECK_SOURCE -->|"No (system)<br/>Skip to prevent loops"| SKIP[Ignore]
    RANDOMIZE -->|"N new test configs<br/>source: system"| SIM_TOPIC

    %% Styling
    classDef storage fill:#f9f,stroke:#333,stroke-width:2px
    classDef topic fill:#bbf,stroke:#333,stroke-width:2px
    classDef decision fill:#ffa,stroke:#333,stroke-width:2px

    class STORE,WHEEL_CACHE storage
    class SIM_TOPIC,RESULTS_TOPIC,SUCCESS_TOPIC,FAILURE_TOPIC topic
    class ROUTE,CHECK_SOURCE decision
```

## Data Flow Details

### 1. Model Upload Flow
```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as HTTP API
    participant Disk as state/models/
    participant Kafka as Kafka

    FE->>API: POST /simulation<br/>{model: {filename, data: base64}, ...}
    API->>Disk: Write model binary
    API->>Kafka: Publish {model: {filename}, ...}<br/>(no binary data)
    API->>FE: 200 OK {message_key}
```

### 2. Simulation Execution Flow
```mermaid
sequenceDiagram
    participant Kafka as Kafka (simulation)
    participant Runner as Simulink Runner
    participant API as HTTP API
    participant Cache as Wheel Cache

    Kafka->>Runner: Message {model: {filename}, config, ...}
    Runner->>Runner: Check wheel cache by filename
    alt Wheel not cached
        Runner->>API: GET /models/{filename}
        API->>Runner: Binary wheel data
        Runner->>Runner: pip install wheel
        Runner->>Cache: Cache loaded module
    end
    Runner->>Runner: Execute simulation
    Runner->>Kafka: Publish results to simulation-results
```

### 3. Validation & Feedback Loop
```mermaid
sequenceDiagram
    participant Results as Kafka (simulation-results)
    participant Val as Validator
    participant Success as Kafka (validation-success)
    participant Failure as Kafka (validation-failure)
    participant TG as Test Generator
    participant Sim as Kafka (simulation)

    Results->>Val: Simulation results
    Val->>Val: Check max(position) >= threshold

    alt Validation Passed
        Val->>Success: Route to success topic
    else Validation Failed
        Val->>Failure: Route to failure topic
        Failure->>TG: Failed validation
        TG->>TG: Check source field
        alt source == "user"
            TG->>TG: Generate N variations (±2-20%, 1-3 outliers ±10-30%)
            TG->>Sim: Publish with source: "system"
            Note over Sim: Loop continues...
        else source == "system"
            TG->>TG: Skip (loop prevention)
        end
    end
```

## Kafka Topics

| Topic | Tier | Purpose |
|-------|------|---------|
| `simulation` | Bronze | Simulation requests (model reference + config) |
| `simulation-results` | Silver | Completed simulations with output data |
| `validation-success` | Gold | Simulations that passed threshold |
| `validation-failure` | Silver | Simulations that failed threshold |

## Key Design Decisions

### Model Storage (Not in Kafka)
- **Problem**: Large model binaries (300MB+) would bloat Kafka messages
- **Solution**: Store models on disk, pass only filename reference in messages
- **Retrieval**: Services fetch models via `GET /models/{filename}` API

### Feedback Loop Prevention
- **Problem**: Generated tests could trigger infinite test generation
- **Solution**: `source` field distinguishes user vs system-initiated requests
- **Rule**: Test Generator only processes `source: "user"` messages

### Model Retention
- Models are stored for 24 hours then automatically cleaned up
- Cleanup runs on HTTP API startup
- Same filename overwrites existing model (no versioning)

## Environment Variables

### HTTP API
| Variable | Description |
|----------|-------------|
| `output` | Kafka topic for simulation requests |
| `HTTP_AUTH_TOKEN` | Bearer token for authentication |

### Simulink Runner
| Variable | Description |
|----------|-------------|
| `input` | Input Kafka topic |
| `output` | Output Kafka topic |
| `API_URL` | URL to fetch models from HTTP API |
| `HTTP_AUTH_TOKEN` | Bearer token for API authentication |

### Test Generator
| Variable | Description |
|----------|-------------|
| `input` | Failed validations topic |
| `output` | Simulation requests topic |
| `NUM_TESTS` | Number of test variations per failure |
