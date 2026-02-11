# FMU Simulation Feedback Loop - Setup Guide

This guide walks you through deploying and configuring the FMU Simulation Feedback Loop on Quix Cloud.

## Step 1: Configure Secrets

The template requires secrets to be configured during synchronization.

### Synchronization Flow

1. **Press the Sync button** in the top right corner of the Quix UI

2. **Quix will prompt you to add secrets** - enter values for any missing secrets

3. **Set all required secrets** - enter secure values for each secret

### Required Secrets

| Secret Key | Used By | Description |
|------------|---------|-------------|
| `http_auth_token` | HTTP API, FMU Runner, Validator | Bearer token of your choice for API authentication |

### Setting Up Secrets

#### HTTP Authentication Token (`http_auth_token`)

This token secures the HTTP API and allows internal services to communicate:

1. **Choose a strong, unique token** (e.g., a UUID or random string)
2. This value will be used by all services to authenticate API requests

**Example:**
```
http_auth_token: my-secure-simulation-token-2024
```

> **Warning:** This token acts as an authentication layer since the HTTP API is publicly accessible. **DO NOT use weak tokens.**

## Step 2: Verify Deployment

After synchronization completes, verify all services are running:

### Core Services

| Service | Status Check |
|---------|--------------|
| **HTTP API** | Web UI accessible via public URL |
| **FMU Runner** | Logs show "Starting Kafka consumer..." |
| **Validator** | Logs show "Starting Kafka consumer..." |
| **Test Generator** | Logs show "Starting Kafka consumer..." |

> **Note:** Services may restart 2-3 times while waiting for dependencies (Kafka topics, etc.). This is normal.

### Checking Service Health

1. Open each service in the Quix UI
2. Check the **Logs** tab for startup messages
3. Verify no persistent error loops

## Step 3: Access the Frontend

1. Click on the **HTTP API** deployment
2. Find the **public URL** link
3. Open in browser - you should see the simulation submission form

### Frontend Features

- **FMU Upload**: Drag and drop FMU files
- **Config Editor**: JSON editor with validation
- **Generate Sample**: Auto-generates config from FMU metadata
- **Run History**: Track submitted simulations and results
- **Run Details**: View parameter variations and success/failure status

## Step 4: Submit Your First Simulation

### Using the BouncingBall Example

1. Download the [BouncingBall.fmu](https://github.com/modelica/fmi-cross-check/raw/master/fmus/2.0/cs/linux64/MapleSim/2021.2/BouncingBall/BouncingBall.fmu) sample FMU

2. Upload it to the frontend

3. Click **Generate Sample** to create a config based on FMU metadata

4. Adjust the config:
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

5. Click **Run Simulation**

6. Watch the Run History for results

## Step 5: Understanding Results

### Run Family

When the original run fails validation, the Test Generator creates parameter variations. All runs sharing a parent are called a "Run Family".

- **Original**: Your submitted configuration
- **Variants**: Auto-generated parameter variations (`_gen_1`, `_gen_2`, etc.)

### Success Criteria

The validator checks: `max(field_name) >= target_value`

- **Passed**: At least one run in the family met the criteria
- **Failed**: No configuration found that meets the criteria

### Viewing Details

Click on any run in the history to see:
- Timeseries charts of simulation outputs
- Parameter differences between variants
- Success/failure status for each run

## Troubleshooting

### Services failing to start

- Verify `http_auth_token` secret is set
- Check that Kafka broker is healthy
- Allow 2-3 restart cycles for initialization

### Simulations not completing

- Check FMU Runner logs for simulation errors
- Verify FMU file is valid (FMI 2.0 compatible)
- Check Validator logs for validation errors

### No parameter variations generated

- Verify Test Generator is running
- Check that the original run **failed** validation (variations only generated on failure)
- Verify config has numeric `parameters` to vary

### Frontend not loading

- Check HTTP API logs for startup errors
- Verify the public URL is correctly configured
- Check browser console for JavaScript errors

## Topics Reference

| Topic | Producer | Consumer |
|-------|----------|----------|
| `simulation` | HTTP API | FMU Runner |
| `simulation-results` | FMU Runner | Validator |
| `validation-success` | Validator | (stored in QuixLake) |
| `validation-failure` | Validator | Test Generator |
