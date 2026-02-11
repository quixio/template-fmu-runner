<script>
    import { createEventDispatcher } from 'svelte';
    import { onMount } from 'svelte';

    export let message = '';
    export let modelName = '';
    export let passed = null;
    export let maxHeight = null;
    export let duration = 5000;
    export let onViewDetails = null;

    const dispatch = createEventDispatcher();

    let visible = false;
    let timeoutId = null;

    onMount(() => {
        // Trigger entrance animation
        requestAnimationFrame(() => {
            visible = true;
        });

        // Auto-dismiss after duration
        if (duration > 0) {
            timeoutId = setTimeout(() => {
                dismiss();
            }, duration);
        }

        return () => {
            if (timeoutId) clearTimeout(timeoutId);
        };
    });

    function dismiss() {
        visible = false;
        setTimeout(() => {
            dispatch('dismiss');
        }, 300); // Wait for exit animation
    }

    function handleViewDetails() {
        if (onViewDetails) {
            onViewDetails();
        }
        dismiss();
    }
</script>

<div class="toast" class:visible class:passed class:failed={passed === false}>
    <div class="toast-icon">
        {#if passed === true}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
        {:else if passed === false}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        {:else}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
        {/if}
    </div>

    <div class="toast-content">
        <div class="toast-title">Simulation Complete</div>
        <div class="toast-model">{modelName}</div>
        <div class="toast-result">
            {#if passed === true}
                PASSED
            {:else if passed === false}
                FAILED
            {:else}
                {message}
            {/if}
            {#if maxHeight !== null}
                <span class="toast-detail">- Max height {maxHeight.toFixed(2)}m</span>
            {/if}
        </div>
    </div>

    <div class="toast-actions">
        {#if onViewDetails}
            <button class="toast-btn view-btn" on:click={handleViewDetails}>
                View
            </button>
        {/if}
        <button class="toast-btn close-btn" on:click={dismiss} title="Dismiss">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        </button>
    </div>
</div>

<style>
    .toast {
        display: flex;
        align-items: flex-start;
        gap: var(--space-md);
        padding: var(--space-md) var(--space-lg);
        background-color: var(--bg-elevated);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        min-width: 320px;
        max-width: 400px;
        transform: translateX(120%);
        opacity: 0;
        transition: transform 0.3s ease, opacity 0.3s ease;
    }

    .toast.visible {
        transform: translateX(0);
        opacity: 1;
    }

    .toast.passed {
        border-color: var(--success);
        background-color: rgba(0, 210, 106, 0.1);
    }

    .toast.failed {
        border-color: var(--error);
        background-color: rgba(255, 71, 87, 0.1);
    }

    .toast-icon {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background-color: var(--bg-secondary);
        flex-shrink: 0;
    }

    .toast.passed .toast-icon {
        background-color: var(--success);
        color: white;
    }

    .toast.failed .toast-icon {
        background-color: var(--error);
        color: white;
    }

    .toast-icon svg {
        width: 18px;
        height: 18px;
    }

    .toast-content {
        flex: 1;
        min-width: 0;
    }

    .toast-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
    }

    .toast-model {
        font-size: 0.75rem;
        color: var(--text-secondary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-top: 2px;
    }

    .toast-result {
        font-size: 0.8125rem;
        font-weight: 500;
        margin-top: 4px;
    }

    .toast.passed .toast-result {
        color: var(--success);
    }

    .toast.failed .toast-result {
        color: var(--error);
    }

    .toast-detail {
        font-weight: 400;
        color: var(--text-secondary);
    }

    .toast-actions {
        display: flex;
        align-items: center;
        gap: var(--space-xs);
        flex-shrink: 0;
    }

    .toast-btn {
        border: none;
        border-radius: var(--radius-sm);
        background-color: transparent;
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .view-btn {
        padding: var(--space-xs) var(--space-sm);
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--accent-primary);
    }

    .view-btn:hover {
        background-color: rgba(0, 210, 106, 0.1);
    }

    .close-btn {
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-muted);
    }

    .close-btn:hover {
        background-color: var(--bg-secondary);
        color: var(--text-primary);
    }

    .close-btn svg {
        width: 14px;
        height: 14px;
    }
</style>
