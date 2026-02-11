<script>
    import { createEventDispatcher } from 'svelte';

    export let filename = '';
    export let data = { headers: [], rows: [] };

    const dispatch = createEventDispatcher();
    const maxRows = 10;

    $: displayRows = data.rows.slice(0, maxRows);
    $: totalRows = data.rows.length;

    function handleReplace() {
        dispatch('replace');
    }
</script>

<div class="preview-container">
    <div class="preview-header">
        <span class="preview-title">
            <svg class="preview-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
            </svg>
            <span>{filename}</span>
        </span>
        <button class="replace-btn" on:click={handleReplace}>Replace File</button>
    </div>
    <div class="table-wrapper">
        <table class="data-table">
            <thead>
                <tr>
                    {#each data.headers as header}
                        <th>{header}</th>
                    {/each}
                </tr>
            </thead>
            <tbody>
                {#each displayRows as row}
                    <tr>
                        {#each row as cell}
                            <td>{cell}</td>
                        {/each}
                    </tr>
                {/each}
            </tbody>
        </table>
    </div>
    <p class="preview-note">
        {#if totalRows > maxRows}
            Showing first {maxRows} rows of {totalRows}
        {:else}
            Showing all {totalRows} rows
        {/if}
    </p>
</div>

<style>
    .preview-container {
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        overflow: hidden;
    }

    .preview-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--space-md);
        background-color: var(--bg-elevated);
        border-bottom: 1px solid var(--border-default);
    }

    .preview-title {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        font-size: 0.875rem;
        color: var(--text-primary);
    }

    .preview-icon {
        width: 18px;
        height: 18px;
        color: var(--accent-primary);
    }

    .replace-btn {
        padding: var(--space-xs) var(--space-md);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--text-secondary);
        font-size: 0.8125rem;
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .replace-btn:hover {
        border-color: var(--accent-primary);
        color: var(--accent-primary);
    }

    .table-wrapper {
        overflow-x: auto;
        max-height: 240px;
        overflow-y: auto;
    }

    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.8125rem;
    }

    .data-table th,
    .data-table td {
        padding: var(--space-sm) var(--space-md);
        text-align: left;
        border-bottom: 1px solid var(--border-default);
    }

    .data-table th {
        background-color: var(--bg-secondary);
        color: var(--text-secondary);
        font-weight: 500;
        position: sticky;
        top: 0;
    }

    .data-table td {
        color: var(--text-primary);
        font-family: 'SF Mono', Monaco, 'Courier New', monospace;
    }

    .data-table tbody tr:hover {
        background-color: var(--bg-elevated);
    }

    .preview-note {
        padding: var(--space-sm) var(--space-md);
        font-size: 0.75rem;
        color: var(--text-muted);
        background-color: var(--bg-secondary);
        margin: 0;
    }
</style>
