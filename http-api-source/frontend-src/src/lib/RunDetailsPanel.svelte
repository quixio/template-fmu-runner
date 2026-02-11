<script>
    import { onMount, onDestroy } from 'svelte';
    import { Chart, registerables } from 'chart.js';

    Chart.register(...registerables);

    export let run = null;
    export let onClose = () => {};

    let loading = true;
    let error = null;
    let details = null;
    let relatedRuns = null;
    let parentRun = null;
    let positionChartCanvas;
    let velocityChartCanvas;
    let positionChart;
    let velocityChart;

    // Reset state and refetch when run changes
    $: if (run?.messageKey) {
        resetAndFetch();
    }

    function resetAndFetch() {
        // Clean up old charts
        positionChart?.destroy();
        velocityChart?.destroy();
        positionChart = null;
        velocityChart = null;

        // Reset state
        loading = true;
        error = null;
        details = null;
        relatedRuns = null;
        parentRun = null;

        // Fetch new data
        fetchRunDetails();
    }

    function formatTimestamp(ts) {
        if (!ts) return '-';
        return new Date(ts).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    function formatDuration(ms) {
        if (!ms || ms < 0) return '-';
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    }

    async function fetchRunDetails() {
        if (!run?.messageKey) {
            error = 'No message key available for this run';
            loading = false;
            return;
        }

        try {
            // Get base URL - strip /simulation suffix if present, fallback to relative path
            const apiBaseUrl = (window.__API_URL__ && !window.__API_URL__.startsWith('__RUNTIME_'))
                ? window.__API_URL__.replace(/\/simulation\/?$/, '')
                : '';
            const authToken = (window.__HTTP_AUTH_TOKEN__ && !window.__HTTP_AUTH_TOKEN__.startsWith('__RUNTIME_'))
                ? window.__HTTP_AUTH_TOKEN__
                : '';

            const headers = {};
            if (authToken) {
                headers['Authorization'] = `Bearer ${authToken}`;
            }

            // Determine which message key to use for details
            // If there's a best variant, fetch that one's data instead
            const detailsKey = run.bestVariantKey || run.messageKey;

            // Fetch run details and related runs in parallel
            const [detailsResponse, relatedResponse] = await Promise.all([
                fetch(`${apiBaseUrl}/runs/${encodeURIComponent(detailsKey)}`, { headers }),
                fetch(`${apiBaseUrl}/runs/${encodeURIComponent(run.messageKey)}/related`, { headers })
            ]);

            if (!detailsResponse.ok) {
                throw new Error(`Failed to fetch run details: ${detailsResponse.statusText}`);
            }

            details = await detailsResponse.json();

            // Related runs are optional - don't fail if not found
            if (relatedResponse.ok) {
                const relatedData = await relatedResponse.json();
                // Sort runs: parent first, then by numeric suffix
                relatedRuns = (relatedData.runs || []).sort((a, b) => {
                    const aKey = a.message_key || '';
                    const bKey = b.message_key || '';
                    const aGen = aKey.match(/_gen_(\d+)$/);
                    const bGen = bKey.match(/_gen_(\d+)$/);
                    // Parent (no _gen_) comes first
                    if (!aGen && bGen) return -1;
                    if (aGen && !bGen) return 1;
                    // Both have _gen_, sort numerically
                    if (aGen && bGen) return parseInt(aGen[1]) - parseInt(bGen[1]);
                    // Neither has _gen_, keep original order
                    return 0;
                });
                parentRun = relatedData.parent_run || null;
            }

            loading = false;

            // Render charts after data is loaded
            setTimeout(() => {
                renderCharts();
            }, 0);
        } catch (err) {
            error = err.message;
            loading = false;
        }
    }

    // Extract config values from a run result (handles flattened config_* fields)
    function extractConfig(result) {
        if (!result) return {};
        const config = {};
        for (const [key, value] of Object.entries(result)) {
            if (key.startsWith('config_')) {
                config[key.replace('config_', '')] = value;
            }
        }
        return config;
    }

    // Get config differences between a run and the parent
    function getConfigDiff(runResult, parentResult) {
        if (!parentResult) {
            console.log('getConfigDiff: parentResult is null/undefined');
            return [];
        }
        const runConfig = extractConfig(runResult);
        const parentConfig = extractConfig(parentResult);
        console.log('getConfigDiff:', {
            runKey: runResult?.message_key,
            runConfig,
            parentKey: parentResult?.message_key,
            parentConfig
        });
        const diffs = [];

        for (const [key, value] of Object.entries(runConfig)) {
            const parentValue = parentConfig[key];
            if (parentValue !== undefined && value !== parentValue) {
                const pctChange = typeof value === 'number' && typeof parentValue === 'number' && parentValue !== 0
                    ? ((value - parentValue) / parentValue * 100).toFixed(1)
                    : null;
                diffs.push({ key, value, parentValue, pctChange });
            }
        }
        return diffs;
    }

    // Check if a run is the parent (no _gen_ suffix)
    function isParentRun(msgKey) {
        return !msgKey?.includes('_gen_');
    }

    // Get run number from message key (e.g., "key_gen_3" -> 3)
    function getRunNumber(msgKey) {
        if (!msgKey?.includes('_gen_')) return 'Original';
        const match = msgKey.match(/_gen_(\d+)$/);
        return match ? `#${match[1]}` : msgKey;
    }

    function renderCharts() {
        if (!details?.timeseries || details.timeseries.length === 0) return;

        const labels = details.timeseries.map((_, i) => i);
        const positions = details.timeseries.map(d => d.position ?? d.x ?? null);
        const velocities = details.timeseries.map(d => d.velocity ?? d.v ?? null);

        // Position chart
        if (positionChartCanvas && positions.some(v => v !== null)) {
            positionChart = new Chart(positionChartCanvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Position',
                        data: positions,
                        borderColor: '#00d26a',
                        backgroundColor: 'rgba(0, 210, 106, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: 'Time Step', color: '#888' },
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        },
                        y: {
                            title: { display: true, text: 'Position', color: '#888' },
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        }
                    }
                }
            });
        }

        // Velocity chart
        if (velocityChartCanvas && velocities.some(v => v !== null)) {
            velocityChart = new Chart(velocityChartCanvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Velocity',
                        data: velocities,
                        borderColor: '#ff9f43',
                        backgroundColor: 'rgba(255, 159, 67, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: 'Time Step', color: '#888' },
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        },
                        y: {
                            title: { display: true, text: 'Velocity', color: '#888' },
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.05)' }
                        }
                    }
                }
            });
        }
    }

    // Note: fetchRunDetails is called reactively when run changes (see $: block above)
    // onMount is not needed for fetching since the reactive statement handles it

    onDestroy(() => {
        positionChart?.destroy();
        velocityChart?.destroy();
    });

    function handleKeydown(e) {
        if (e.key === 'Escape') {
            onClose();
        }
    }

    function handleBackdropClick(e) {
        if (e.target === e.currentTarget) {
            onClose();
        }
    }

    $: validationPassed = details?.result?.validation_passed ?? details?.result?.passed ?? null;
    $: validationReason = details?.result?.validation_reason ?? details?.result?.reason ?? '';
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="details-backdrop" on:click={handleBackdropClick} on:keydown={() => {}} role="dialog" aria-modal="true">
    <div class="details-modal">
        <div class="details-header">
            <div class="header-info">
                <h2 class="header-title">Run Details</h2>
                <span class="header-subtitle">{run?.messageKey || run?.modelFilename || 'Unknown'}</span>
            </div>
            <button class="close-btn" on:click={onClose} title="Close (Esc)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>

        <div class="details-content">
            {#if loading}
                <div class="loading-state">
                    <div class="spinner"></div>
                    <p>Loading run details...</p>
                </div>
            {:else if error}
                <div class="error-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    <p>{error}</p>
                </div>
            {:else if details}
                <!-- Validation Banner -->
                <div class="validation-banner" class:passed={validationPassed} class:failed={validationPassed === false}>
                    <div class="validation-icon">
                        {#if validationPassed}
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"/>
                            </svg>
                        {:else if validationPassed === false}
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        {:else}
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="12" y1="16" x2="12" y2="12"/>
                                <line x1="12" y1="8" x2="12.01" y2="8"/>
                            </svg>
                        {/if}
                    </div>
                    <div class="validation-text">
                        <span class="validation-status">
                            {validationPassed === true ? 'Validation Passed' : validationPassed === false ? 'Validation Failed' : 'Unknown Status'}
                        </span>
                        {#if validationReason}
                            <span class="validation-reason">{validationReason}</span>
                        {/if}
                    </div>
                </div>

                <!-- Statistics Grid -->
                {#if details.statistics}
                    <div class="stats-grid">
                        <div class="stat-card">
                            <span class="stat-value">{details.statistics.data_points ?? '-'}</span>
                            <span class="stat-label">Data Points</span>
                        </div>
                        <div class="stat-card">
                            <span class="stat-value">{details.statistics.max_position?.toFixed(3) ?? '-'}</span>
                            <span class="stat-label">Max Position</span>
                        </div>
                        <div class="stat-card">
                            <span class="stat-value">{details.statistics.max_velocity?.toFixed(3) ?? '-'}</span>
                            <span class="stat-label">Max Velocity</span>
                        </div>
                        <div class="stat-card">
                            <span class="stat-value">{formatDuration(details.statistics.duration_ms)}</span>
                            <span class="stat-label">Duration</span>
                        </div>
                    </div>
                {/if}

                <!-- Configuration -->
                {#if details.result?.config}
                    <div class="config-section">
                        <h3 class="section-title">Configuration</h3>
                        <div class="config-grid">
                            {#each Object.entries(details.result.config) as [key, value]}
                                <div class="config-item">
                                    <span class="config-key">{key}</span>
                                    <span class="config-value">{typeof value === 'object' ? JSON.stringify(value) : value}</span>
                                </div>
                            {/each}
                        </div>
                    </div>
                {/if}

                <!-- Charts -->
                {#if details.timeseries && details.timeseries.length > 0}
                    <div class="charts-section">
                        <h3 class="section-title">Time Series</h3>
                        <div class="charts-grid">
                            <div class="chart-container">
                                <h4 class="chart-title">Position</h4>
                                <div class="chart-wrapper">
                                    <canvas bind:this={positionChartCanvas}></canvas>
                                </div>
                            </div>
                            <div class="chart-container">
                                <h4 class="chart-title">Velocity</h4>
                                <div class="chart-wrapper">
                                    <canvas bind:this={velocityChartCanvas}></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                {:else}
                    <div class="no-timeseries">
                        <p>No time series data available for this run.</p>
                    </div>
                {/if}

                <!-- Timestamps -->
                <div class="timestamps-section">
                    <h3 class="section-title">Timestamps</h3>
                    <div class="timestamps-grid">
                        <div class="timestamp-item">
                            <span class="timestamp-label">Submitted</span>
                            <span class="timestamp-value">{formatTimestamp(details.result?.submitted_at || run?.timestamp)}</span>
                        </div>
                        <div class="timestamp-item">
                            <span class="timestamp-label">Started</span>
                            <span class="timestamp-value">{formatTimestamp(details.result?.started_at)}</span>
                        </div>
                        <div class="timestamp-item">
                            <span class="timestamp-label">Completed</span>
                            <span class="timestamp-value">{formatTimestamp(details.result?.completed_at)}</span>
                        </div>
                    </div>
                </div>

                <!-- Generated Variations -->
                {#if relatedRuns && relatedRuns.length >= 1}
                    <div class="variations-section">
                        <h3 class="section-title">{relatedRuns.length > 1 ? `Run Family (${relatedRuns.length} runs)` : 'Run Details'}</h3>
                        {#if relatedRuns.length > 1}
                            <p class="variations-description">
                                When the original run fails validation, the system generates config variations to find parameters that meet the success criteria.
                            </p>
                        {/if}
                        <div class="variations-table-wrapper">
                            <table class="variations-table">
                                <thead>
                                    <tr>
                                        <th class="col-run">Run</th>
                                        <th class="col-status">Status</th>
                                        <th class="col-height">Max Value</th>
                                        <th class="col-config">Config Changes</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {#each relatedRuns as relRun}
                                        {@const isPassed = relRun.validation_passed}
                                        {@const isOriginal = isParentRun(relRun.message_key)}
                                        {@const maxHeight = relRun.validation_calculated_value}
                                        {@const targetValue = relRun.config_success_criteria_target_value ?? relRun.threshold}
                                        {@const configDiffs = isOriginal ? [] : getConfigDiff(relRun, parentRun)}
                                        <tr class:passed={isPassed} class:failed={isPassed === false} class:original={isOriginal}>
                                            <td class="col-run">
                                                <span class="run-number">{getRunNumber(relRun.message_key)}</span>
                                                {#if isOriginal}
                                                    <span class="original-badge">Original</span>
                                                {/if}
                                                {#if relRun.source === 'system'}
                                                    <span class="system-badge">Auto</span>
                                                {/if}
                                            </td>
                                            <td class="col-status">
                                                <span class="status-badge" class:passed={isPassed} class:failed={isPassed === false}>
                                                    {#if isPassed}
                                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                            <polyline points="20 6 9 17 4 12"/>
                                                        </svg>
                                                        Passed
                                                    {:else if isPassed === false}
                                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                            <line x1="18" y1="6" x2="6" y2="18"/>
                                                            <line x1="6" y1="6" x2="18" y2="18"/>
                                                        </svg>
                                                        Failed
                                                    {:else}
                                                        -
                                                    {/if}
                                                </span>
                                            </td>
                                            <td class="col-height">
                                                {#if maxHeight !== null && maxHeight !== undefined}
                                                    <span class="height-value" class:meets-target={targetValue != null && maxHeight >= targetValue}>
                                                        {maxHeight.toFixed(2)}
                                                    </span>
                                                    {#if targetValue != null}
                                                        <span class="target-note">/ {targetValue}</span>
                                                    {/if}
                                                {:else}
                                                    -
                                                {/if}
                                            </td>
                                            <td class="col-config">
                                                {#if isOriginal}
                                                    <span class="config-original">Baseline config</span>
                                                {:else if configDiffs.length > 0}
                                                    <div class="config-diffs">
                                                        {#each configDiffs as diff}
                                                            <span class="config-diff">
                                                                <span class="diff-key">{diff.key}:</span>
                                                                <span class="diff-value">{typeof diff.value === 'number' ? diff.value.toFixed(3) : diff.value}</span>
                                                                {#if diff.pctChange}
                                                                    <span class="diff-pct" class:positive={parseFloat(diff.pctChange) > 0} class:negative={parseFloat(diff.pctChange) < 0}>
                                                                        ({diff.pctChange > 0 ? '+' : ''}{diff.pctChange}%)
                                                                    </span>
                                                                {/if}
                                                            </span>
                                                        {/each}
                                                    </div>
                                                {:else}
                                                    <span class="no-changes">No changes detected</span>
                                                {/if}
                                            </td>
                                        </tr>
                                    {/each}
                                </tbody>
                            </table>
                        </div>

                        <!-- Summary of successful runs -->
                        {#if relatedRuns.filter(r => r.validation_passed).length > 0}
                            {@const successfulRuns = relatedRuns.filter(r => r.validation_passed)}
                            <div class="success-summary">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="20 6 9 17 4 12"/>
                                </svg>
                                <span>
                                    {successfulRuns.length} of {relatedRuns.length} runs passed validation.
                                    Best result: {Math.max(...successfulRuns.map(r => r.validation_calculated_value || 0)).toFixed(2)}m
                                </span>
                            </div>
                        {:else}
                            <div class="failure-summary">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"/>
                                    <line x1="12" y1="8" x2="12" y2="12"/>
                                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                                </svg>
                                <span>No runs have passed validation yet. The system may still be generating variations.</span>
                            </div>
                        {/if}
                    </div>
                {/if}
            {/if}
        </div>
    </div>
</div>

<style>
    .details-backdrop {
        position: fixed;
        inset: 0;
        background-color: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        padding: var(--space-xl);
    }

    .details-modal {
        width: 100%;
        max-width: 900px;
        max-height: 90vh;
        background-color: var(--bg-primary);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .details-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--space-md) var(--space-lg);
        background-color: var(--bg-secondary);
        border-bottom: 1px solid var(--border-default);
    }

    .header-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .header-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
    }

    .header-subtitle {
        font-size: 0.75rem;
        color: var(--text-muted);
        font-family: monospace;
    }

    .close-btn {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: none;
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--text-secondary);
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .close-btn:hover {
        background-color: var(--bg-elevated);
        color: var(--text-primary);
    }

    .close-btn svg {
        width: 18px;
        height: 18px;
    }

    .details-content {
        flex: 1;
        overflow-y: auto;
        padding: var(--space-lg);
    }

    /* Loading and Error States */
    .loading-state, .error-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: var(--space-xxl);
        color: var(--text-muted);
    }

    .spinner {
        width: 32px;
        height: 32px;
        border: 3px solid var(--border-default);
        border-top-color: var(--accent-primary);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .error-state svg {
        width: 48px;
        height: 48px;
        margin-bottom: var(--space-md);
        color: var(--error);
    }

    /* Validation Banner */
    .validation-banner {
        display: flex;
        align-items: center;
        gap: var(--space-md);
        padding: var(--space-md) var(--space-lg);
        border-radius: var(--radius-md);
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-default);
        margin-bottom: var(--space-lg);
    }

    .validation-banner.passed {
        background-color: rgba(0, 210, 106, 0.1);
        border-color: var(--success);
    }

    .validation-banner.failed {
        background-color: rgba(255, 71, 87, 0.1);
        border-color: var(--error);
    }

    .validation-icon {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background-color: var(--bg-elevated);
    }

    .validation-banner.passed .validation-icon {
        background-color: var(--success);
        color: white;
    }

    .validation-banner.failed .validation-icon {
        background-color: var(--error);
        color: white;
    }

    .validation-icon svg {
        width: 18px;
        height: 18px;
    }

    .validation-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .validation-status {
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .validation-reason {
        font-size: 0.8125rem;
        color: var(--text-secondary);
    }

    /* Statistics Grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: var(--space-md);
        margin-bottom: var(--space-lg);
    }

    .stat-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: var(--space-md);
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
    }

    .stat-value {
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--text-primary);
        font-family: monospace;
    }

    .stat-label {
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 2px;
    }

    /* Configuration Section */
    .section-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-secondary);
        margin: 0 0 var(--space-sm) 0;
    }

    .config-section {
        margin-bottom: var(--space-lg);
    }

    .config-grid {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-sm);
    }

    .config-item {
        display: flex;
        align-items: center;
        gap: var(--space-xs);
        padding: var(--space-xs) var(--space-sm);
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-sm);
    }

    .config-key {
        font-size: 0.75rem;
        color: var(--text-muted);
    }

    .config-value {
        font-size: 0.8125rem;
        color: var(--text-primary);
        font-family: monospace;
    }

    /* Charts Section */
    .charts-section {
        margin-bottom: var(--space-lg);
    }

    .charts-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: var(--space-lg);
    }

    .chart-container {
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        padding: var(--space-md);
    }

    .chart-title {
        font-size: 0.8125rem;
        font-weight: 500;
        color: var(--text-secondary);
        margin: 0 0 var(--space-sm) 0;
    }

    .chart-wrapper {
        height: 200px;
        position: relative;
    }

    .no-timeseries {
        padding: var(--space-lg);
        text-align: center;
        color: var(--text-muted);
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        margin-bottom: var(--space-lg);
    }

    /* Timestamps Section */
    .timestamps-section {
        margin-bottom: var(--space-md);
    }

    .timestamps-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: var(--space-md);
    }

    .timestamp-item {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .timestamp-label {
        font-size: 0.75rem;
        color: var(--text-muted);
    }

    .timestamp-value {
        font-size: 0.8125rem;
        color: var(--text-primary);
    }

    /* Variations Section */
    .variations-section {
        margin-top: var(--space-lg);
        padding-top: var(--space-lg);
        border-top: 1px solid var(--border-default);
    }

    .variations-description {
        font-size: 0.8125rem;
        color: var(--text-muted);
        margin: 0 0 var(--space-md) 0;
    }

    .variations-table-wrapper {
        overflow-x: auto;
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
    }

    .variations-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8125rem;
    }

    .variations-table th,
    .variations-table td {
        padding: var(--space-sm) var(--space-md);
        text-align: left;
        border-bottom: 1px solid var(--border-default);
    }

    .variations-table th {
        background-color: var(--bg-secondary);
        font-weight: 600;
        color: var(--text-secondary);
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }

    .variations-table tbody tr {
        background-color: var(--bg-card);
        transition: background-color var(--transition-fast);
    }

    .variations-table tbody tr:hover {
        background-color: var(--bg-elevated);
    }

    .variations-table tbody tr:last-child td {
        border-bottom: none;
    }

    .variations-table tbody tr.original {
        background-color: var(--bg-secondary);
    }

    .variations-table tbody tr.passed {
        background-color: rgba(0, 210, 106, 0.05);
    }

    .variations-table tbody tr.passed:hover {
        background-color: rgba(0, 210, 106, 0.1);
    }

    .col-run {
        white-space: nowrap;
    }

    .run-number {
        font-family: monospace;
        font-weight: 500;
        color: var(--text-primary);
    }

    .original-badge,
    .system-badge {
        display: inline-block;
        font-size: 0.625rem;
        font-weight: 600;
        padding: 1px 4px;
        border-radius: var(--radius-sm);
        margin-left: var(--space-xs);
        text-transform: uppercase;
    }

    .original-badge {
        background-color: rgba(99, 102, 241, 0.15);
        color: #818cf8;
    }

    .system-badge {
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
    }

    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .status-badge svg {
        width: 14px;
        height: 14px;
    }

    .status-badge.passed {
        color: var(--success);
    }

    .status-badge.failed {
        color: var(--error);
    }

    .height-value {
        font-family: monospace;
        font-weight: 500;
        color: var(--text-primary);
    }

    .height-value.meets-target {
        color: var(--success);
    }

    .target-note {
        font-size: 0.6875rem;
        color: var(--text-muted);
        margin-left: 2px;
    }

    .config-original {
        font-style: italic;
        color: var(--text-muted);
    }

    .config-diffs {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-xs);
    }

    .config-diff {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        padding: 2px 6px;
        background-color: var(--bg-secondary);
        border-radius: var(--radius-sm);
        font-size: 0.75rem;
    }

    .diff-key {
        color: var(--text-muted);
    }

    .diff-value {
        font-family: monospace;
        color: var(--text-primary);
    }

    .diff-pct {
        font-size: 0.6875rem;
        margin-left: 2px;
    }

    .diff-pct.positive {
        color: var(--success);
    }

    .diff-pct.negative {
        color: var(--error);
    }

    .no-changes {
        color: var(--text-muted);
        font-style: italic;
    }

    .success-summary,
    .failure-summary {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        margin-top: var(--space-md);
        padding: var(--space-sm) var(--space-md);
        border-radius: var(--radius-md);
        font-size: 0.8125rem;
    }

    .success-summary {
        background-color: rgba(0, 210, 106, 0.1);
        color: var(--success);
    }

    .failure-summary {
        background-color: rgba(245, 158, 11, 0.1);
        color: #f59e0b;
    }

    .success-summary svg,
    .failure-summary svg {
        width: 18px;
        height: 18px;
        flex-shrink: 0;
    }

    /* Responsive */
    @media (max-width: 768px) {
        .stats-grid {
            grid-template-columns: repeat(2, 1fr);
        }

        .charts-grid {
            grid-template-columns: 1fr;
        }

        .timestamps-grid {
            grid-template-columns: 1fr;
        }

        .variations-table {
            font-size: 0.75rem;
        }

        .variations-table th,
        .variations-table td {
            padding: var(--space-xs) var(--space-sm);
        }
    }
</style>
