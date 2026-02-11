<script>
    import { createEventDispatcher } from 'svelte';
    import { runHistory } from './stores/runHistory.js';

    const dispatch = createEventDispatcher();

    let selectedForCompare = [];
    let expanded = true;

    function handleRunClick(run) {
        dispatch('select', { run });
    }

    function toggleCompareSelection(e, runId) {
        e.stopPropagation();
        if (selectedForCompare.includes(runId)) {
            selectedForCompare = selectedForCompare.filter(id => id !== runId);
        } else if (selectedForCompare.length < 2) {
            selectedForCompare = [...selectedForCompare, runId];
        }
    }

    function handleCompare() {
        const runs = $runHistory.filter(r => selectedForCompare.includes(r.id));
        // Sort by selection order
        runs.sort((a, b) => selectedForCompare.indexOf(a.id) - selectedForCompare.indexOf(b.id));
        dispatch('compare', { runs });
        selectedForCompare = [];
    }

    function handleDelete(e, id) {
        e.stopPropagation();
        runHistory.deleteRun(id);
        selectedForCompare = selectedForCompare.filter(sid => sid !== id);
    }

    function handleViewDetails(e, run) {
        e.stopPropagation();
        dispatch('viewDetails', { run });
    }

    function handleClearAll() {
        if (confirm('Clear all run history?')) {
            runHistory.clearAll();
            selectedForCompare = [];
        }
    }

    function formatTimestamp(ts) {
        const date = new Date(ts);
        return date.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function getStatusClass(run) {
        // Check completion status first
        if (run.completionStatus === 'complete') {
            return run.validationPassed ? 'status-validation-passed' : 'status-validation-failed';
        }
        if (run.completionStatus === 'timeout') {
            return 'status-timeout';
        }
        // Check if polling (has messageKey but not complete)
        if (run.messageKey && !run.completionStatus) {
            return 'status-polling';
        }
        // Fall back to submission status
        if (run.status === 'success') return 'status-submitted';
        if (run.status === 'error') return 'status-error';
        return 'status-pending';
    }

    function getStatusText(run) {
        if (run.completionStatus === 'complete') {
            return run.validationPassed ? 'Passed' : 'Failed';
        }
        if (run.completionStatus === 'timeout') {
            return 'Timeout';
        }
        if (run.messageKey && !run.completionStatus) {
            return 'Processing...';
        }
        return null;
    }
</script>

<div class="history-panel" class:collapsed={!expanded}>
    <div class="panel-header">
        <button class="toggle-btn" on:click={() => expanded = !expanded} title={expanded ? 'Collapse' : 'Expand'}>
            <svg class="toggle-icon" class:rotated={!expanded} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 18 9 12 15 6"/>
            </svg>
        </button>
        {#if expanded}
            <h2 class="panel-title">Run History</h2>
            {#if $runHistory.length > 0}
                <button class="clear-btn" on:click={handleClearAll} title="Clear all">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            {/if}
        {/if}
    </div>

    {#if expanded}
        <div class="panel-content">
            {#if $runHistory.length === 0}
                <div class="empty-state">
                    <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <p>No runs yet</p>
                    <p class="empty-hint">Submit a simulation to see it here</p>
                </div>
            {:else}
                <div class="runs-list">
                    {#each $runHistory as run (run.id)}
                        <div
                            class="run-item"
                            class:selected={selectedForCompare.includes(run.id)}
                            on:click={() => handleRunClick(run)}
                            on:keydown={(e) => e.key === 'Enter' && handleRunClick(run)}
                            role="button"
                            tabindex="0"
                        >
                            <div class="run-checkbox">
                                <input
                                    type="checkbox"
                                    checked={selectedForCompare.includes(run.id)}
                                    disabled={!selectedForCompare.includes(run.id) && selectedForCompare.length >= 2}
                                    on:click={(e) => toggleCompareSelection(e, run.id)}
                                    title="Select for comparison"
                                />
                            </div>
                            <div class="run-info">
                                <div class="run-header">
                                    <span class="run-time">{formatTimestamp(run.timestamp)}</span>
                                    <span class="run-status {getStatusClass(run)}"></span>
                                    {#if getStatusText(run)}
                                        <span class="run-status-badge {getStatusClass(run)}">{getStatusText(run)}</span>
                                    {/if}
                                </div>
                                <div class="run-model" title={run.modelFilename}>
                                    {run.modelFilename}
                                </div>
                                <div class="run-criteria">
                                    {#if run.configJson}
                                        {@const config = JSON.parse(run.configJson || '{}')}
                                        {#if config.success_criteria}
                                            {config.success_criteria.field_name} &ge; {config.success_criteria.target_value}
                                        {/if}
                                    {/if}
                                </div>
                            </div>
                            <div class="run-actions">
                                {#if run.messageKey}
                                    <button
                                        class="details-btn"
                                        on:click={(e) => handleViewDetails(e, run)}
                                        title="View details"
                                    >
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                            <circle cx="12" cy="12" r="3"/>
                                        </svg>
                                    </button>
                                {/if}
                                <button
                                    class="delete-btn"
                                    on:click={(e) => handleDelete(e, run.id)}
                                    title="Delete run"
                                >
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <line x1="18" y1="6" x2="6" y2="18"/>
                                        <line x1="6" y1="6" x2="18" y2="18"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>

        {#if selectedForCompare.length === 2}
            <div class="panel-footer">
                <button class="compare-btn" on:click={handleCompare}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="20" x2="18" y2="10"/>
                        <line x1="12" y1="20" x2="12" y2="4"/>
                        <line x1="6" y1="20" x2="6" y2="14"/>
                    </svg>
                    Compare Selected
                </button>
            </div>
        {/if}
    {/if}
</div>

<style>
    .history-panel {
        display: flex;
        flex-direction: column;
        width: 300px;
        background-color: var(--bg-secondary);
        border-right: 1px solid var(--border-default);
        transition: width var(--transition-normal);
        overflow: hidden;
    }

    .history-panel.collapsed {
        width: 48px;
    }

    .panel-header {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        padding: var(--space-md);
        border-bottom: 1px solid var(--border-default);
        min-height: 56px;
    }

    .toggle-btn {
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
        flex-shrink: 0;
    }

    .toggle-btn:hover {
        background-color: var(--bg-elevated);
        color: var(--text-primary);
    }

    .toggle-icon {
        width: 18px;
        height: 18px;
        transition: transform var(--transition-normal);
    }

    .toggle-icon.rotated {
        transform: rotate(180deg);
    }

    .panel-title {
        flex: 1;
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
        white-space: nowrap;
    }

    .clear-btn {
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: none;
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--text-muted);
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .clear-btn:hover {
        background-color: rgba(255, 71, 87, 0.1);
        color: var(--error);
    }

    .clear-btn svg {
        width: 16px;
        height: 16px;
    }

    .panel-content {
        flex: 1;
        overflow-y: auto;
        padding: var(--space-sm);
    }

    .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: var(--space-xl);
        text-align: center;
        color: var(--text-muted);
    }

    .empty-icon {
        width: 48px;
        height: 48px;
        margin-bottom: var(--space-md);
        opacity: 0.5;
    }

    .empty-state p {
        margin: 0;
        font-size: 0.875rem;
    }

    .empty-hint {
        margin-top: var(--space-xs) !important;
        font-size: 0.75rem !important;
        opacity: 0.7;
    }

    .runs-list {
        display: flex;
        flex-direction: column;
        gap: var(--space-xs);
    }

    .run-item {
        display: flex;
        align-items: flex-start;
        gap: var(--space-sm);
        padding: var(--space-sm) var(--space-md);
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .run-item:hover {
        border-color: var(--border-hover);
        background-color: var(--bg-elevated);
    }

    .run-item.selected {
        border-color: var(--accent-primary);
        background-color: rgba(0, 210, 106, 0.05);
    }

    .run-checkbox {
        padding-top: 2px;
    }

    .run-checkbox input {
        width: 16px;
        height: 16px;
        cursor: pointer;
        accent-color: var(--accent-primary);
    }

    .run-checkbox input:disabled {
        opacity: 0.3;
        cursor: not-allowed;
    }

    .run-info {
        flex: 1;
        min-width: 0;
    }

    .run-header {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        margin-bottom: 2px;
    }

    .run-time {
        font-size: 0.75rem;
        color: var(--text-muted);
    }

    .run-status {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .status-submitted {
        background-color: var(--accent-primary);
    }

    .status-error {
        background-color: var(--error);
    }

    .status-pending {
        background-color: var(--text-muted);
    }

    .status-polling {
        background-color: var(--accent-primary);
        animation: pulse 1.5s ease-in-out infinite;
    }

    .status-validation-passed {
        background-color: var(--success);
    }

    .status-validation-failed {
        background-color: var(--error);
    }

    .status-timeout {
        background-color: var(--text-muted);
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    .run-status-badge {
        font-size: 0.625rem;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: var(--radius-sm);
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }

    .run-status-badge.status-polling {
        background-color: rgba(0, 210, 106, 0.15);
        color: var(--accent-primary);
    }

    .run-status-badge.status-validation-passed {
        background-color: rgba(0, 210, 106, 0.15);
        color: var(--success);
    }

    .run-status-badge.status-validation-failed {
        background-color: rgba(255, 71, 87, 0.15);
        color: var(--error);
    }

    .run-status-badge.status-timeout {
        background-color: rgba(128, 128, 128, 0.15);
        color: var(--text-muted);
    }

    .run-model {
        font-size: 0.8125rem;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 2px;
    }

    .run-criteria {
        font-size: 0.75rem;
        color: var(--text-secondary);
    }

    .run-actions {
        display: flex;
        align-items: center;
        gap: var(--space-xs);
        flex-shrink: 0;
    }

    .details-btn {
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: none;
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--text-muted);
        cursor: pointer;
        opacity: 0;
        transition: all var(--transition-fast);
    }

    .run-item:hover .details-btn {
        opacity: 1;
    }

    .details-btn:hover {
        background-color: rgba(0, 210, 106, 0.1);
        color: var(--accent-primary);
    }

    .details-btn svg {
        width: 14px;
        height: 14px;
    }

    .delete-btn {
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: none;
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--text-muted);
        cursor: pointer;
        opacity: 0;
        transition: all var(--transition-fast);
        flex-shrink: 0;
    }

    .run-item:hover .delete-btn {
        opacity: 1;
    }

    .delete-btn:hover {
        background-color: rgba(255, 71, 87, 0.1);
        color: var(--error);
    }

    .delete-btn svg {
        width: 14px;
        height: 14px;
    }

    .panel-footer {
        padding: var(--space-md);
        border-top: 1px solid var(--border-default);
    }

    .compare-btn {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-sm);
        padding: var(--space-sm) var(--space-md);
        border: none;
        border-radius: var(--radius-md);
        background-color: var(--accent-primary);
        color: var(--bg-primary);
        font-size: 0.875rem;
        font-weight: 600;
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .compare-btn:hover {
        background-color: var(--accent-hover);
    }

    .compare-btn svg {
        width: 16px;
        height: 16px;
    }
</style>
