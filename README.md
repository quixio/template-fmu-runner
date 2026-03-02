# FMU Runner

[![Tests](https://github.com/quixio/template-fmu-runner/actions/workflows/tests.yml/badge.svg)](https://github.com/quixio/template-fmu-runner/actions/workflows/tests.yml)

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

## Tests

The project includes a pytest-based test suite that validates the FMU simulation logic against all 25 [Reference FMUs](https://github.com/modelica/Reference-FMUs) (v0.0.39) across FMI 1.0, 2.0, and 3.0. Tests cover unit functions, integration with real simulations, and end-to-end message processing.

### Running Tests

**Windows:**
```bash
cd fmu-runner
run_tests.bat
```

**macOS / Linux:**
```bash
cd fmu-runner
./run_tests.sh
```

**Manual (any platform):**
```bash
cd fmu-runner
pip install -r requirements-test.txt
python -m pytest tests/ -v
```

### Coverage by FMI Version (183 tests)

All reference FMUs are stored in `fmu-runner/tests/fixtures/` organized by version.

| Version | FMUs Tested | Tests |
|---------|-------------|-------|
| **FMI 1.0 CS** | BouncingBall, Dahlquist, Feedthrough, Resource, Stair, VanDerPol | 22 |
| **FMI 1.0 ME** | BouncingBall, Dahlquist, Feedthrough, Stair, VanDerPol | 18 |
| **FMI 2.0** | BouncingBall, Dahlquist, Feedthrough, Resource, Stair, VanDerPol | 59 |
| **FMI 3.0** | BouncingBall, Clocks, Dahlquist, Feedthrough, Resource, Stair, StateSpace, VanDerPol | 30 |
| **Unit tests** | Pure functions, format_output, error handling | 54 |

### Reference FMUs

| FMU | Description | Outputs | Parameters |
|-----|-------------|---------|------------|
| **BouncingBall** | Ball dropped from 1m height with elastic bouncing | `h` (height), `v` (velocity) | `g` (gravity), `e` (restitution) |
| **Dahlquist** | Linear ODE test equation (dx/dt = -k·x) | `x` | `k` (decay rate) |
| **Feedthrough** | Mixed-type I/O passthrough (Real, Integer, Boolean, String, Enumeration) | 6 typed outputs (16 in FMI 3.0) | `Float64_fixed_parameter`, `Float64_tunable_parameter` |
| **VanDerPol** | Van der Pol nonlinear oscillator | `x0`, `x1` | `mu` (nonlinearity) |
| **Resource** | Loads data from a bundled resource file | `y` | — |
| **Stair** | Step counter using time events | `counter` | — |
| **Clocks** (3.0 only) | ScheduledExecution clock synchronization | Clock ticks, counters | — |
| **StateSpace** (3.0 only) | State-space system with matrix parameters | `y` | `A`, `B`, `C`, `D` matrices, `x0` |

> **Note:** Clocks.fmu is a ScheduledExecution-only FMU (not CoSimulation or ModelExchange), which fmpy cannot simulate. Tests verify metadata is readable and that simulation returns a clean error. StateSpace.fmu uses array-valued structural parameters; tests verify it doesn't crash.

### Example Simulation Output

**BouncingBall** — ball dropped from h=1m, bounces with restitution e=0.7:
```
time      h          v
0.0000    1.00000    0.00000
0.0100    0.99956   -0.09810
0.0200    0.99814   -0.19620
0.0300    0.99573   -0.29430
0.0400    0.99235   -0.39240
0.0500    0.98798   -0.49050
...
3.0000    0.00000    0.00000
```

**Dahlquist** — exponential decay dx/dt = -x, x(0) = 1:
```
time      x
0.0000    1.000000
0.1000    0.900000
0.2000    0.810000
0.3000    0.729000
...
3.0000    0.042391      (analytical: e^-3 ≈ 0.0498)
```

**VanDerPol** — nonlinear oscillator, x0(0) = 2, x1(0) = 0:
```
time       x0          x1
 0.000     2.00000     0.00000
 2.000     0.33411    -1.82007
 4.000    -1.76169     0.62260
 6.000     1.20369     2.54362
 8.000     1.26474    -0.95287
10.000    -2.02638    -0.06794
12.000    -0.45516     1.69325
14.000     1.80393    -0.59069
16.000    -1.02156    -2.65883
18.000    -1.32925     0.90702
20.000     2.01484     0.24419
```

### Example Test Run

```
$ python -m pytest tests/ -v
========================= test session starts =========================

tests/test_fmu_executor.py::TestShouldProcess::test_fmu_extension PASSED
tests/test_fmu_executor.py::TestShouldProcess::test_fmu_extension_uppercase PASSED
...
tests/test_fmu_executor.py::TestFmi20BouncingBall::test_completes PASSED
tests/test_fmu_executor.py::TestFmi20BouncingBall::test_initial_conditions PASSED
tests/test_fmu_executor.py::TestFmi20BouncingBall::test_height_nonnegative PASSED
tests/test_fmu_executor.py::TestFmi20Dahlquist::test_exponential_decay PASSED
tests/test_fmu_executor.py::TestFmi20VanDerPol::test_oscillates PASSED
...
tests/test_fmu_executor.py::TestFmi10CsBouncingBall::test_completes PASSED
tests/test_fmu_executor.py::TestFmi10MeVanDerPol::test_oscillates PASSED
tests/test_fmu_executor.py::TestFmi30BouncingBall::test_has_h_ft_output PASSED
tests/test_fmu_executor.py::TestFmi30Clocks::test_simulation_returns_error PASSED
tests/test_fmu_executor.py::TestFmi30StateSpace::test_has_structural_parameters PASSED
...
tests/test_main.py::TestProcessMessage::test_valid_request_completes PASSED
tests/test_main.py::TestProcessMessage::test_timestamps_are_utc_iso PASSED
tests/test_main.py::TestProcessMessage::test_nonexistent_fmu_returns_error PASSED
...

==================== 180 passed, 3 xfailed in 8.08s ====================
```
