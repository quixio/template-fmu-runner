<script>
    import { onMount, onDestroy } from 'svelte';
    import { MergeView } from '@codemirror/merge';
    import { EditorState } from '@codemirror/state';
    import { EditorView } from '@codemirror/view';
    import { json } from '@codemirror/lang-json';
    import { quixTheme } from './theme.js';

    export let leftRun = null;
    export let rightRun = null;
    export let onClose = () => {};

    let container;
    let mergeView;

    function formatTimestamp(ts) {
        return new Date(ts).toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    function prettifyJson(jsonStr) {
        try {
            return JSON.stringify(JSON.parse(jsonStr), null, 2);
        } catch {
            return jsonStr;
        }
    }

    onMount(() => {
        if (leftRun && rightRun && container) {
            const leftDoc = prettifyJson(leftRun.configJson);
            const rightDoc = prettifyJson(rightRun.configJson);

            mergeView = new MergeView({
                a: {
                    doc: leftDoc,
                    extensions: [
                        json(),
                        quixTheme,
                        EditorState.readOnly.of(true),
                        EditorView.lineWrapping
                    ]
                },
                b: {
                    doc: rightDoc,
                    extensions: [
                        json(),
                        quixTheme,
                        EditorState.readOnly.of(true),
                        EditorView.lineWrapping
                    ]
                },
                parent: container,
                highlightChanges: true,
                gutter: true
            });
        }
    });

    onDestroy(() => {
        mergeView?.destroy();
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

    // Extract success_criteria from configJson
    function getSuccessCriteria(run) {
        if (!run?.configJson) return null;
        try {
            const config = JSON.parse(run.configJson);
            return config?.success_criteria || null;
        } catch {
            return null;
        }
    }

    $: leftCriteria = getSuccessCriteria(leftRun);
    $: rightCriteria = getSuccessCriteria(rightRun);
    $: criteriaChanged = JSON.stringify(leftCriteria) !== JSON.stringify(rightCriteria);
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="comparison-backdrop" on:click={handleBackdropClick} on:keydown={() => {}} role="dialog" aria-modal="true">
    <div class="comparison-modal">
        <div class="comparison-header">
            <div class="comparison-titles">
                <div class="run-label">
                    <span class="label-time">{formatTimestamp(leftRun.timestamp)}</span>
                    <span class="label-model">{leftRun.modelFilename}</span>
                </div>
                <span class="vs">vs</span>
                <div class="run-label">
                    <span class="label-time">{formatTimestamp(rightRun.timestamp)}</span>
                    <span class="label-model">{rightRun.modelFilename}</span>
                </div>
            </div>
            <button class="close-btn" on:click={onClose} title="Close (Esc)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>

        <div class="comparison-content" bind:this={container}></div>

        <div class="comparison-footer">
            <div class="meta-diff">
                {#if leftCriteria || rightCriteria}
                    <div class="meta-item">
                        <span class="meta-label">Success Criteria:</span>
                        <span class="meta-value" class:changed={criteriaChanged}>
                            {#if leftCriteria}
                                {leftCriteria.field_name} &ge; {leftCriteria.target_value}
                            {:else}
                                (none)
                            {/if}
                            {#if criteriaChanged}
                                <span class="arrow">→</span>
                                {#if rightCriteria}
                                    {rightCriteria.field_name} &ge; {rightCriteria.target_value}
                                {:else}
                                    (none)
                                {/if}
                            {/if}
                        </span>
                    </div>
                {/if}
                {#if leftRun.modelFilename !== rightRun.modelFilename}
                    <div class="meta-item">
                        <span class="meta-label">Model changed:</span>
                        <span class="meta-value changed">
                            {leftRun.modelFilename} → {rightRun.modelFilename}
                        </span>
                    </div>
                {/if}
            </div>
        </div>
    </div>
</div>

<style>
    .comparison-backdrop {
        position: fixed;
        inset: 0;
        background-color: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        padding: var(--space-xl);
    }

    .comparison-modal {
        width: 100%;
        max-width: 1200px;
        max-height: 90vh;
        background-color: var(--bg-primary);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .comparison-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--space-md) var(--space-lg);
        background-color: var(--bg-secondary);
        border-bottom: 1px solid var(--border-default);
    }

    .comparison-titles {
        display: flex;
        align-items: center;
        gap: var(--space-lg);
    }

    .run-label {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .label-time {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .label-model {
        font-size: 0.75rem;
        color: var(--text-secondary);
    }

    .vs {
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
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

    .comparison-content {
        flex: 1;
        overflow: auto;
        min-height: 300px;
    }

    /* MergeView styling */
    .comparison-content :global(.cm-mergeView) {
        height: 100%;
    }

    .comparison-content :global(.cm-mergeView-panel) {
        display: flex;
    }

    .comparison-content :global(.cm-mergeViewEditor) {
        flex: 1;
        min-width: 0;
    }

    .comparison-content :global(.cm-editor) {
        height: 100%;
        min-height: 400px;
    }

    .comparison-content :global(.cm-scroller) {
        font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        font-size: 13px;
    }

    .comparison-content :global(.cm-changedLine) {
        background-color: rgba(0, 210, 106, 0.1) !important;
    }

    .comparison-content :global(.cm-deletedChunk) {
        background-color: rgba(255, 71, 87, 0.15) !important;
    }

    .comparison-content :global(.cm-insertedChunk) {
        background-color: rgba(0, 210, 106, 0.15) !important;
    }

    .comparison-content :global(.cm-changedText) {
        background-color: rgba(0, 210, 106, 0.25) !important;
    }

    .comparison-content :global(.cm-deletedText) {
        background-color: rgba(255, 71, 87, 0.3) !important;
    }

    .comparison-content :global(.cm-insertedText) {
        background-color: rgba(0, 210, 106, 0.3) !important;
    }

    .comparison-footer {
        padding: var(--space-md) var(--space-lg);
        background-color: var(--bg-secondary);
        border-top: 1px solid var(--border-default);
    }

    .meta-diff {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-lg);
    }

    .meta-item {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
    }

    .meta-label {
        font-size: 0.8125rem;
        color: var(--text-muted);
    }

    .meta-value {
        font-size: 0.8125rem;
        color: var(--text-primary);
    }

    .meta-value.changed {
        color: var(--accent-primary);
    }

    .arrow {
        color: var(--text-muted);
        margin: 0 var(--space-xs);
    }
</style>
