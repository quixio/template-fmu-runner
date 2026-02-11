<script>
    import { createEventDispatcher } from 'svelte';

    export let accept = '';

    const dispatch = createEventDispatcher();

    let dragover = false;
    let inputElement;

    function handleDragOver(e) {
        e.preventDefault();
        dragover = true;
    }

    function handleDragLeave() {
        dragover = false;
    }

    function handleDrop(e) {
        e.preventDefault();
        dragover = false;

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            dispatch('file', { file: files[0] });
        }
    }

    function handleClick() {
        inputElement.click();
    }

    function handleInputChange(e) {
        if (e.target.files.length > 0) {
            dispatch('file', { file: e.target.files[0] });
        }
    }

    function handleInputClick(e) {
        // Stop propagation to prevent the parent div's click handler
        // from triggering inputElement.click() again
        e.stopPropagation();
    }
</script>

<div
    class="dropzone"
    class:dragover
    on:dragover={handleDragOver}
    on:dragleave={handleDragLeave}
    on:drop={handleDrop}
    on:click={handleClick}
    on:keydown={(e) => e.key === 'Enter' && handleClick()}
    role="button"
    tabindex="0"
>
    <div class="dropzone-content">
        <svg class="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <slot />
    </div>
    <input
        type="file"
        {accept}
        bind:this={inputElement}
        on:click={handleInputClick}
        on:change={handleInputChange}
        class="file-input"
    />
</div>

<style>
    .dropzone {
        position: relative;
        border: 2px dashed var(--border-default);
        border-radius: var(--radius-lg);
        background-color: var(--bg-card);
        padding: var(--space-xl);
        text-align: center;
        cursor: pointer;
        transition: all var(--transition-normal);
    }

    .dropzone:hover {
        border-color: var(--border-hover);
        background-color: var(--bg-elevated);
    }

    .dropzone.dragover {
        border-color: var(--accent-primary);
        background-color: var(--accent-muted);
    }

    .dropzone-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-sm);
    }

    .dropzone-icon {
        width: 48px;
        height: 48px;
        color: var(--text-muted);
        margin-bottom: var(--space-sm);
    }

    .file-input {
        position: absolute;
        inset: 0;
        opacity: 0;
        cursor: pointer;
    }
</style>
