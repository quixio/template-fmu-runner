<script>
    import './app.css';
    import { onMount, onDestroy } from 'svelte';
    import Dropzone from './lib/Dropzone.svelte';
    import CsvPreview from './lib/CsvPreview.svelte';
    import JsonEditor from './lib/JsonEditor.svelte';
    import RunHistoryPanel from './lib/RunHistoryPanel.svelte';
    import ComparisonView from './lib/ComparisonView.svelte';
    import RunDetailsPanel from './lib/RunDetailsPanel.svelte';
    import Toast from './lib/Toast.svelte';
    import { runHistory } from './lib/stores/runHistory.js';
    import { startPolling, completionEvents, isPolling } from './lib/stores/runPolling.js';

    // Form state
    let modelFile = null;
    let modelFilename = null;  // Filename from history (model already on server)
    let csvFile = null;
    let csvData = null;
    let jsonContent = '';
    let jsonValid = true;
    let submitting = false;

    // FMU metadata state
    let fmuMetadata = null;
    let fmuMetadataLoading = false;
    let fmuMetadataError = null;

    // Comparison state
    let showComparison = false;
    let comparisonRuns = [];

    // Run details state
    let showRunDetails = false;
    let selectedRunForDetails = null;

    // Status message (shown next to submit button)
    let statusMessage = null;  // { type: 'success' | 'error', text: string }

    // Toast notifications
    let toasts = [];

    // Default config with success_criteria example
    const defaultConfig = {
        start_time: 0,
        stop_time: 10,
        parameters: {},
        success_criteria: {
            field_name: "h",
            target_value: 1.0
        }
    };

    // Initialize with default config
    jsonContent = JSON.stringify(defaultConfig, null, 2);

    // Subscribe to completion events for toast notifications
    // Track shown notifications to prevent duplicates
    const shownNotifications = new Set();
    const unsubscribe = completionEvents.subscribe(event => {
        if (event && !shownNotifications.has(event.messageKey)) {
            shownNotifications.add(event.messageKey);

            // Find the run in history to get model name
            const runs = [];
            runHistory.subscribe(r => runs.push(...r))();
            const run = runs.find(r => r.id === event.runId);

            // Use family result - _family_passed is true if ANY run in the family passed
            const passed = event.data._family_passed ?? event.data.validation_passed ?? event.data.validation?.passed;
            const calculatedValue = event.data.validation_calculated_value ?? event.data.validation?.calculated_value;

            toasts = [...toasts, {
                id: Date.now(),
                modelName: run?.modelFilename || 'Unknown',
                passed,
                calculatedValue,
                runId: event.runId,
                messageKey: event.messageKey
            }];
        }
    });

    onDestroy(() => {
        unsubscribe();
    });

    // Resume polling for incomplete runs on page load
    onMount(() => {
        const runs = [];
        const unsub = runHistory.subscribe(r => { runs.length = 0; runs.push(...r); });
        unsub();

        // Find runs that were submitted but haven't completed yet
        const incompleteRuns = runs.filter(r =>
            r.status === 'success' &&
            r.messageKey &&
            !r.completionStatus &&
            !isPolling(r.messageKey)
        );

        if (incompleteRuns.length > 0) {
            console.log(`[App] Resuming polling for ${incompleteRuns.length} incomplete run(s)`);
            for (const run of incompleteRuns) {
                console.log(`[App] Resuming poll for: ${run.messageKey}`);
                startPolling(run.messageKey, run.id);
            }
        }
    });

    function dismissToast(id) {
        toasts = toasts.filter(t => t.id !== id);
    }

    function handleToastViewDetails(toast) {
        // Find the run and open details
        const runs = [];
        runHistory.subscribe(r => runs.push(...r))();
        const run = runs.find(r => r.id === toast.runId);
        if (run) {
            selectedRunForDetails = run;
            showRunDetails = true;
        }
        dismissToast(toast.id);
    }

    // Computed: do we have a model (either uploaded or from history)?
    $: hasModel = modelFile !== null || modelFilename !== null;

    // Handle model file upload
    async function handleModelFile(event) {
        modelFile = event.detail.file;
        modelFilename = null;  // Clear history filename when uploading new file
        fmuMetadata = null;
        fmuMetadataError = null;

        // Fetch FMU metadata after uploading
        if (modelFile) {
            await uploadAndFetchFmuMetadata(modelFile);
        }
    }

    async function uploadAndFetchFmuMetadata(file) {
        fmuMetadataLoading = true;
        fmuMetadataError = null;

        try {
            // First, upload the model to S3 via the API
            const authToken = (window.__HTTP_AUTH_TOKEN__ && !window.__HTTP_AUTH_TOKEN__.startsWith('__RUNTIME_'))
                ? window.__HTTP_AUTH_TOKEN__
                : '';

            // Upload model via a simple POST with the file data
            const uploadPayload = {
                model_filename: file.name,
                model_data: await fileToBase64(file),
                input_data: [],
                config: {}
            };

            const headers = { 'Content-Type': 'application/json' };
            if (authToken) {
                headers['Authorization'] = `Bearer ${authToken}`;
            }

            // Submit to trigger model storage in S3 - response includes S3 paths
            const uploadResponse = await fetch('/simulation', {
                method: 'POST',
                headers,
                body: JSON.stringify(uploadPayload)
            });

            if (!uploadResponse.ok) {
                throw new Error('Failed to upload model');
            }

            const uploadResult = await uploadResponse.json();
            const modelS3Path = uploadResult.model_s3_path;

            if (!modelS3Path) {
                throw new Error('No S3 path returned from upload');
            }

            // Now fetch the metadata using the S3 path
            const metadataResponse = await fetch(`/models/${encodeURIComponent(modelS3Path)}/metadata`, {
                headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
            });

            if (metadataResponse.ok) {
                const data = await metadataResponse.json();
                if (data.success) {
                    fmuMetadata = data;
                    // Update config with first output as default field_name
                    if (data.variables?.outputs?.length > 0) {
                        updateConfigWithOutput(data.variables.outputs[0].name);
                    }
                }
            } else {
                fmuMetadataError = 'Failed to load FMU metadata';
            }
        } catch (err) {
            console.error('Error fetching FMU metadata:', err);
            fmuMetadataError = err.message || 'Failed to load FMU metadata';
        } finally {
            fmuMetadataLoading = false;
        }
    }

    function updateConfigWithOutput(outputName) {
        try {
            const config = JSON.parse(jsonContent);
            if (!config.success_criteria) {
                config.success_criteria = {};
            }
            config.success_criteria.field_name = outputName;
            jsonContent = JSON.stringify(config, null, 2);
        } catch {
            // Ignore if JSON is invalid
        }
    }

    function generateSampleConfig() {
        if (!fmuMetadata) return;

        const config = {
            start_time: 0,
            stop_time: 10,
            parameters: {},
            success_criteria: {
                field_name: '',
                target_value: 1.0
            }
        };

        // Add parameters with their default values
        if (fmuMetadata.variables?.parameters) {
            for (const param of fmuMetadata.variables.parameters) {
                if (param.start !== null && param.start !== undefined) {
                    config.parameters[param.name] = param.start;
                }
            }
        }

        // Set first output as default field_name
        if (fmuMetadata.variables?.outputs?.length > 0) {
            config.success_criteria.field_name = fmuMetadata.variables.outputs[0].name;
        }

        jsonContent = JSON.stringify(config, null, 2);
        jsonValid = true;
    }

    function removeModel() {
        modelFile = null;
        modelFilename = null;
        fmuMetadata = null;
        fmuMetadataError = null;
    }

    // Handle CSV file upload
    function handleCsvFile(event) {
        csvFile = event.detail.file;
        const reader = new FileReader();
        reader.onload = (e) => {
            csvData = parseCSV(e.target.result);
        };
        reader.readAsText(csvFile);
    }

    function replaceCsv() {
        csvFile = null;
        csvData = null;
    }

    function parseCSV(text) {
        const lines = text.trim().split('\n');
        const headers = lines[0].split(',').map(h => h.trim());
        const rows = lines.slice(1).map(line =>
            line.split(',').map(cell => cell.trim())
        );
        return { headers, rows };
    }

    // Handle JSON content change
    function handleJsonChange(event) {
        jsonContent = event.detail.content;
        jsonValid = event.detail.valid;
    }

    // Form submission
    async function handleSubmit() {
        if (!hasModel || !csvFile || !jsonContent.trim()) {
            statusMessage = { type: 'error', text: 'Please fill in all fields' };
            return;
        }

        if (!jsonValid) {
            statusMessage = { type: 'error', text: 'Please fix JSON validation errors' };
            return;
        }

        // Validate success_criteria in config
        try {
            const config = JSON.parse(jsonContent);
            if (!config.success_criteria?.field_name) {
                statusMessage = { type: 'error', text: 'Config must include success_criteria.field_name' };
                return;
            }
            if (config.success_criteria.target_value === undefined) {
                statusMessage = { type: 'error', text: 'Config must include success_criteria.target_value' };
                return;
            }
        } catch {
            statusMessage = { type: 'error', text: 'Invalid JSON config' };
            return;
        }

        submitting = true;
        statusMessage = null;

        // Determine model info
        const currentModelFilename = modelFile ? modelFile.name : modelFilename;

        // Save run to history before submission
        const runId = runHistory.addRun({
            modelFilename: currentModelFilename,
            configJson: jsonContent,
            csvFilename: csvFile.name,
            csvData: csvData,
            status: 'submitted'
        });

        try {
            const payload = {
                model_filename: currentModelFilename,
                // Include model_data only if we have a new file upload
                ...(modelFile && { model_data: await fileToBase64(modelFile) }),
                input_data: csvData.rows.map((row, idx) => {
                    const obj = {};
                    csvData.headers.forEach((header, i) => {
                        obj[header] = row[i];
                    });
                    return obj;
                }),
                config: JSON.parse(jsonContent)
            };

            // Get API URL and auth token from runtime config (injected by server)
            // Falls back to relative path when served from same origin
            const apiUrl = (window.__API_URL__ && !window.__API_URL__.startsWith('__RUNTIME_'))
                ? window.__API_URL__
                : '/simulation';
            const authToken = (window.__HTTP_AUTH_TOKEN__ && !window.__HTTP_AUTH_TOKEN__.startsWith('__RUNTIME_'))
                ? window.__HTTP_AUTH_TOKEN__
                : '';

            const headers = {
                'Content-Type': 'application/json'
            };
            if (authToken) {
                headers['Authorization'] = `Bearer ${authToken}`;
            }

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers,
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const responseData = await response.json();
                const messageKey = responseData.message_key || null;
                runHistory.updateRunStatus(runId, 'success', null, messageKey);
                statusMessage = { type: 'success', text: 'Simulation submitted' };

                // Start polling for completion
                if (messageKey) {
                    startPolling(messageKey, runId);
                }
            } else {
                const error = await response.text();
                runHistory.updateRunStatus(runId, 'error', error);
                statusMessage = { type: 'error', text: error };
            }
        } catch (error) {
            console.error('Submission error:', error);
            runHistory.updateRunStatus(runId, 'error', error.message);
            statusMessage = { type: 'error', text: error.message };
        } finally {
            submitting = false;
        }
    }

    // Handle selecting a run from history to populate the form
    function handleSelectRun(event) {
        const { run } = event.detail;

        // Populate form fields
        jsonContent = run.configJson;
        jsonValid = true;

        // Restore CSV if available
        if (run.csvData) {
            csvData = run.csvData;
            csvFile = { name: run.csvFilename };
        }

        // Use stored model filename - model binary is already on server
        modelFile = null;
        modelFilename = run.modelFilename;
    }

    // Handle comparison request
    function handleCompare(event) {
        comparisonRuns = event.detail.runs;
        showComparison = true;
    }

    function closeComparison() {
        showComparison = false;
        comparisonRuns = [];
    }

    // Handle view details request
    function handleViewDetails(event) {
        selectedRunForDetails = event.detail.run;
        showRunDetails = true;
    }

    function closeRunDetails() {
        showRunDetails = false;
        selectedRunForDetails = null;
    }

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const base64 = reader.result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
</script>

<div class="app-layout">
    <RunHistoryPanel
        on:select={handleSelectRun}
        on:compare={handleCompare}
        on:viewDetails={handleViewDetails}
    />

    <div class="form-container">
        <h1 class="form-title">FMU Simulation</h1>

        <!-- FMU Model Upload -->
        <div class="form-section">
            <span class="section-label">FMU Model</span>
            {#if modelFile}
                <div class="file-display">
                    <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span class="file-name">{modelFile.name}</span>
                    <button class="remove-btn" on:click={removeModel} title="Remove file">×</button>
                </div>
            {:else if modelFilename}
                <div class="file-display file-display--from-history">
                    <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span class="file-name">{modelFilename}</span>
                    <span class="from-history-badge">from history</span>
                    <button class="remove-btn" on:click={removeModel} title="Remove">×</button>
                </div>
            {:else}
                <Dropzone accept=".fmu" on:file={handleModelFile}>
                    <p class="dropzone-text">Drag & drop your FMU file here</p>
                    <p class="dropzone-subtext">Functional Mock-up Unit (.fmu)</p>
                </Dropzone>
            {/if}
        </div>

        <!-- FMU Metadata Display -->
        {#if fmuMetadataLoading}
            <div class="fmu-metadata-section">
                <div class="fmu-loading">Loading FMU metadata...</div>
            </div>
        {:else if fmuMetadataError}
            <div class="fmu-metadata-section">
                <div class="fmu-error">{fmuMetadataError}</div>
            </div>
        {:else if fmuMetadata}
            <div class="fmu-metadata-section">
                <div class="fmu-model-info">
                    <h3>{fmuMetadata.modelInfo.modelName}</h3>
                    <div class="fmu-info-row">
                        <span class="fmu-label">FMI Version:</span>
                        <span class="fmu-value">{fmuMetadata.modelInfo.fmiVersion}</span>
                    </div>
                    {#if fmuMetadata.modelInfo.description}
                        <div class="fmu-info-row">
                            <span class="fmu-label">Description:</span>
                            <span class="fmu-value">{fmuMetadata.modelInfo.description}</span>
                        </div>
                    {/if}
                </div>

                <div class="fmu-variables-grid">
                    {#if fmuMetadata.variables.inputs.length > 0}
                        <div class="fmu-var-section">
                            <h4>Inputs <span class="fmu-count">{fmuMetadata.variables.inputs.length}</span></h4>
                            <table class="fmu-var-table">
                                <thead>
                                    <tr><th>Name</th><th>Type</th><th>Start</th></tr>
                                </thead>
                                <tbody>
                                    {#each fmuMetadata.variables.inputs as v}
                                        <tr>
                                            <td><code>{v.name}</code></td>
                                            <td><span class="fmu-type-badge">{v.type}</span></td>
                                            <td>{v.start ?? '-'}</td>
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>
                    {/if}

                    {#if fmuMetadata.variables.outputs.length > 0}
                        <div class="fmu-var-section">
                            <h4>Outputs <span class="fmu-count">{fmuMetadata.variables.outputs.length}</span>
                                <span class="fmu-hint">Use in success_criteria.field_name</span>
                            </h4>
                            <table class="fmu-var-table">
                                <thead>
                                    <tr><th>Name</th><th>Type</th><th>Description</th></tr>
                                </thead>
                                <tbody>
                                    {#each fmuMetadata.variables.outputs as v}
                                        <tr>
                                            <td><code>{v.name}</code></td>
                                            <td><span class="fmu-type-badge">{v.type}</span></td>
                                            <td class="fmu-desc">{v.description || '-'}</td>
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>
                    {/if}

                    {#if fmuMetadata.variables.parameters.length > 0}
                        <div class="fmu-var-section">
                            <h4>Parameters <span class="fmu-count">{fmuMetadata.variables.parameters.length}</span>
                                <span class="fmu-hint">Override in config.parameters</span>
                            </h4>
                            <table class="fmu-var-table">
                                <thead>
                                    <tr><th>Name</th><th>Type</th><th>Default</th></tr>
                                </thead>
                                <tbody>
                                    {#each fmuMetadata.variables.parameters as v}
                                        <tr>
                                            <td><code>{v.name}</code></td>
                                            <td><span class="fmu-type-badge">{v.type}</span></td>
                                            <td>{v.start ?? '-'}</td>
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>
                    {/if}
                </div>
            </div>
        {/if}

        <!-- CSV Input Data -->
        <div class="form-section">
            <span class="section-label">Input Data (CSV)</span>
            {#if csvData}
                <CsvPreview
                    filename={csvFile.name}
                    data={csvData}
                    on:replace={replaceCsv}
                />
            {:else}
                <Dropzone accept=".csv" on:file={handleCsvFile}>
                    <p class="dropzone-text">Drag & drop your CSV file here</p>
                    <p class="dropzone-subtext">Must include 'time' column and FMU input columns</p>
                </Dropzone>
            {/if}
        </div>

        <!-- JSON Configuration -->
        <div class="form-section">
            <div class="section-header">
                <span class="section-label">Configuration (JSON)</span>
                {#if fmuMetadata}
                    <button class="generate-config-btn" on:click={generateSampleConfig} title="Generate sample config from FMU metadata">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/>
                        </svg>
                        Generate Sample
                    </button>
                {/if}
            </div>
            <div class="config-hint">
                Define <code>success_criteria.field_name</code> (output to check) and <code>success_criteria.target_value</code> (threshold)
            </div>
            <JsonEditor
                bind:content={jsonContent}
                bind:valid={jsonValid}
                on:change={handleJsonChange}
            />
        </div>

        <!-- Submit Button -->
        <div class="form-actions">
            <button class="submit-btn" on:click={handleSubmit} disabled={submitting}>
                <span>{submitting ? 'Submitting...' : 'Run Simulation'}</span>
                {#if !submitting}
                    <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                {/if}
            </button>
            {#if statusMessage}
                <span class="status-message status-message--{statusMessage.type}">
                    {statusMessage.text}
                </span>
            {/if}
        </div>
    </div>
</div>

{#if showComparison && comparisonRuns.length === 2}
    <ComparisonView
        leftRun={comparisonRuns[0]}
        rightRun={comparisonRuns[1]}
        onClose={closeComparison}
    />
{/if}

{#if showRunDetails && selectedRunForDetails}
    <RunDetailsPanel
        run={selectedRunForDetails}
        onClose={closeRunDetails}
    />
{/if}

<!-- Toast notifications -->
<div class="toast-container">
    {#each toasts as toast (toast.id)}
        <Toast
            modelName={toast.modelName}
            passed={toast.passed}
            maxHeight={toast.calculatedValue}
            onViewDetails={() => handleToastViewDetails(toast)}
            on:dismiss={() => dismissToast(toast.id)}
        />
    {/each}
</div>

<style>
    .toast-container {
        position: fixed;
        top: var(--space-lg);
        right: var(--space-lg);
        z-index: 1100;
        display: flex;
        flex-direction: column;
        gap: var(--space-sm);
    }

    .app-layout {
        display: flex;
        min-height: 100vh;
        width: 100%;
    }

    .form-container {
        flex: 1;
        padding: var(--space-xl);
        overflow-y: auto;
    }

    .file-display--from-history {
        border-color: var(--accent-primary);
        background-color: rgba(0, 210, 106, 0.05);
    }

    .from-history-badge {
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: var(--radius-sm);
        background-color: var(--accent-muted);
        color: var(--accent-primary);
    }

    .form-title {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: var(--space-xl);
        color: var(--text-primary);
    }

    .form-section {
        margin-bottom: var(--space-lg);
    }

    .section-label {
        display: block;
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--text-secondary);
        margin-bottom: var(--space-sm);
    }

    .section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: var(--space-sm);
    }

    .section-header .section-label {
        margin-bottom: 0;
    }

    .generate-config-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.375rem 0.75rem;
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--text-secondary);
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        cursor: pointer;
        transition: all 0.15s ease;
    }

    .generate-config-btn:hover {
        color: var(--accent);
        border-color: var(--accent);
        background: rgba(99, 102, 241, 0.1);
    }

    .generate-config-btn svg {
        width: 14px;
        height: 14px;
    }

    .config-hint {
        font-size: 0.8125rem;
        color: var(--text-muted);
        margin-bottom: var(--space-sm);
    }

    .config-hint code {
        background-color: var(--bg-elevated);
        padding: 1px 4px;
        border-radius: var(--radius-sm);
        font-family: var(--font-mono, monospace);
        color: var(--accent-primary);
    }

    /* File display (for uploaded model) */
    .file-display {
        display: flex;
        align-items: center;
        gap: var(--space-md);
        padding: var(--space-md);
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
    }

    .file-icon {
        width: 24px;
        height: 24px;
        color: var(--accent-primary);
    }

    .file-name {
        flex: 1;
        font-size: 0.9375rem;
        color: var(--text-primary);
    }

    .remove-btn {
        width: 28px;
        height: 28px;
        border: none;
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--text-muted);
        font-size: 1.25rem;
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .remove-btn:hover {
        background-color: var(--error);
        color: var(--text-primary);
    }

    /* Dropzone text */
    .dropzone-text {
        font-size: 1rem;
        color: var(--text-primary);
        margin: 0;
    }

    .dropzone-subtext {
        font-size: 0.875rem;
        color: var(--text-muted);
        margin: 0;
    }

    /* Submit button */
    .form-actions {
        display: flex;
        align-items: center;
        gap: var(--space-md);
        margin-top: var(--space-xl);
        padding-top: var(--space-lg);
        border-top: 1px solid var(--border-default);
    }

    .status-message {
        font-size: 0.875rem;
        font-weight: 500;
    }

    .status-message--success {
        color: var(--success);
    }

    .status-message--error {
        color: var(--error);
    }

    .submit-btn {
        display: inline-flex;
        align-items: center;
        gap: var(--space-sm);
        padding: var(--space-md) var(--space-xl);
        border: none;
        border-radius: var(--radius-md);
        background-color: var(--accent-primary);
        color: var(--bg-primary);
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .submit-btn:hover:not(:disabled) {
        background-color: var(--accent-hover);
        transform: translateY(-1px);
    }

    .submit-btn:active:not(:disabled) {
        transform: translateY(0);
    }

    .submit-btn:disabled {
        opacity: 0.7;
        cursor: not-allowed;
    }

    .btn-icon {
        width: 18px;
        height: 18px;
    }

    /* FMU Metadata Styles */
    .fmu-metadata-section {
        margin-bottom: var(--space-lg);
        padding: var(--space-lg);
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
    }

    .fmu-loading {
        color: var(--text-muted);
        font-size: 0.875rem;
        text-align: center;
        padding: var(--space-md);
    }

    .fmu-error {
        color: var(--error);
        font-size: 0.875rem;
        text-align: center;
        padding: var(--space-md);
    }

    .fmu-model-info {
        margin-bottom: var(--space-lg);
        padding-bottom: var(--space-md);
        border-bottom: 1px solid var(--border-default);
    }

    .fmu-model-info h3 {
        margin: 0 0 var(--space-sm) 0;
        font-size: 1.125rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .fmu-info-row {
        display: flex;
        gap: var(--space-sm);
        margin-bottom: var(--space-xs);
        font-size: 0.875rem;
    }

    .fmu-label {
        color: var(--text-muted);
        min-width: 100px;
    }

    .fmu-value {
        color: var(--text-secondary);
    }

    .fmu-variables-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: var(--space-lg);
    }

    .fmu-var-section h4 {
        margin: 0 0 var(--space-sm) 0;
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: var(--space-sm);
    }

    .fmu-count {
        font-size: 0.75rem;
        font-weight: 500;
        padding: 2px 6px;
        border-radius: var(--radius-sm);
        background-color: var(--accent-muted);
        color: var(--accent-primary);
    }

    .fmu-hint {
        font-size: 0.7rem;
        font-weight: 400;
        color: var(--text-muted);
        margin-left: auto;
    }

    .fmu-var-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8125rem;
    }

    .fmu-var-table th {
        text-align: left;
        padding: var(--space-xs) var(--space-sm);
        color: var(--text-muted);
        font-weight: 500;
        border-bottom: 1px solid var(--border-default);
    }

    .fmu-var-table td {
        padding: var(--space-xs) var(--space-sm);
        color: var(--text-secondary);
        border-bottom: 1px solid var(--border-subtle);
    }

    .fmu-var-table tr:last-child td {
        border-bottom: none;
    }

    .fmu-var-table code {
        font-family: var(--font-mono, monospace);
        font-size: 0.8rem;
        color: var(--text-primary);
    }

    .fmu-type-badge {
        display: inline-block;
        padding: 1px 6px;
        border-radius: var(--radius-sm);
        background-color: var(--bg-elevated);
        color: var(--text-muted);
        font-size: 0.75rem;
        font-family: var(--font-mono, monospace);
    }

    .fmu-desc {
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
</style>
