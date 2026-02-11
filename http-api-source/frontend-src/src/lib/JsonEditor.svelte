<script>
    import { createEventDispatcher } from 'svelte';
    import CodeMirror from 'svelte-codemirror-editor';
    import { json } from '@codemirror/lang-json';
    import { quixTheme } from './theme.js';

    export let content = '';
    export let valid = true;

    const dispatch = createEventDispatcher();

    let errorMessage = '';
    let fileInputElement;
    let uploadDragover = false;
    let editorDragover = false;

    // Show validation status only when there's content
    $: showValidation = content.trim().length > 0;
    $: if (showValidation) {
        validateJson(content);
    } else {
        valid = true;
        errorMessage = '';
    }

    function validateJson(text) {
        try {
            JSON.parse(text);
            valid = true;
            errorMessage = '';
        } catch (err) {
            valid = false;
            errorMessage = err.message;
        }
    }

    function handleChange(value) {
        dispatch('change', { content: value, valid: showValidation ? valid : true });
    }

    function handlePrettify() {
        try {
            const parsed = JSON.parse(content);
            const prettified = JSON.stringify(parsed, null, 2);
            content = prettified;
            dispatch('change', { content: prettified, valid: true });
        } catch {
            // Can't prettify invalid JSON
        }
    }

    function handleUploadClick() {
        fileInputElement.click();
    }

    function handleFileInput(e) {
        if (e.target.files.length > 0) {
            loadFile(e.target.files[0]);
        }
        // Reset input so same file can be selected again
        e.target.value = '';
    }

    function loadFile(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const parsed = JSON.parse(e.target.result);
                content = JSON.stringify(parsed, null, 2);
                valid = true;
                errorMessage = '';
            } catch {
                content = e.target.result;
                validateJson(content);
            }
            dispatch('change', { content, valid });
        };
        reader.readAsText(file);
    }

    // Drag and drop on upload button
    function handleUploadDragOver(e) {
        e.preventDefault();
        uploadDragover = true;
    }

    function handleUploadDragLeave() {
        uploadDragover = false;
    }

    function handleUploadDrop(e) {
        e.preventDefault();
        uploadDragover = false;
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            loadFile(files[0]);
        }
    }

    // Drag and drop on editor area
    function handleEditorDragOver(e) {
        e.preventDefault();
        editorDragover = true;
    }

    function handleEditorDragLeave(e) {
        // Only set to false if leaving the wrapper entirely
        if (!e.currentTarget.contains(e.relatedTarget)) {
            editorDragover = false;
        }
    }

    function handleEditorDrop(e) {
        e.preventDefault();
        editorDragover = false;
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            loadFile(files[0]);
        }
    }
</script>

<div class="editor-container">
    <div class="editor-header">
        <div class="editor-actions">
            {#if showValidation}
                <span class="validation-status" class:valid class:invalid={!valid}>
                    {#if valid}
                        <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                        Valid JSON
                    {:else}
                        <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="15" y1="9" x2="9" y2="15"/>
                            <line x1="9" y1="9" x2="15" y2="15"/>
                        </svg>
                        Invalid JSON
                    {/if}
                </span>
            {/if}
            <button class="action-btn" on:click={handlePrettify} disabled={!valid || !showValidation}>Prettify</button>
            <button
                class="upload-btn"
                class:dragover={uploadDragover}
                on:click={handleUploadClick}
                on:dragover={handleUploadDragOver}
                on:dragleave={handleUploadDragLeave}
                on:drop={handleUploadDrop}
                title="Drop file here"
            >
                <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                Upload
            </button>
            <input
                type="file"
                accept=".json"
                bind:this={fileInputElement}
                on:change={handleFileInput}
                class="hidden-input"
            />
        </div>
    </div>
    <div
        class="codemirror-wrapper"
        class:dragover={editorDragover}
        on:dragover={handleEditorDragOver}
        on:dragleave={handleEditorDragLeave}
        on:drop={handleEditorDrop}
        role="region"
        aria-label="JSON editor - drop files here"
    >
        <CodeMirror
            bind:value={content}
            lang={json()}
            theme={quixTheme}
            on:change={(e) => handleChange(e.detail)}
            placeholder="Paste or type JSON configuration here..."
            styles={{
                '&': {
                    minHeight: '240px',
                    fontSize: '13px',
                },
                '.cm-gutters': {
                    borderRight: '1px solid #2a2a45',
                },
                '.cm-scroller': {
                    fontFamily: "'SF Mono', Monaco, 'Courier New', monospace",
                },
                '.cm-placeholder': {
                    color: '#6b6b80',
                },
            }}
        />
    </div>
    {#if !valid && errorMessage}
        <div class="validation-error">
            <svg class="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="error-text">Error: {errorMessage}</span>
        </div>
    {/if}
</div>

<style>
    .editor-container {
        background-color: var(--bg-card);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        overflow: hidden;
    }

    .editor-header {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding: var(--space-md);
        background-color: var(--bg-elevated);
        border-bottom: 1px solid var(--border-default);
        flex-wrap: wrap;
        gap: var(--space-sm);
    }

    .editor-actions {
        display: flex;
        align-items: center;
        gap: var(--space-md);
        flex-wrap: wrap;
    }

    .validation-status {
        display: flex;
        align-items: center;
        gap: var(--space-xs);
        font-size: 0.8125rem;
        padding: var(--space-xs) var(--space-sm);
        border-radius: var(--radius-sm);
    }

    .validation-status.valid {
        color: var(--success);
        background-color: rgba(0, 210, 106, 0.1);
    }

    .validation-status.invalid {
        color: var(--error);
        background-color: rgba(255, 71, 87, 0.1);
    }

    .status-icon {
        width: 14px;
        height: 14px;
    }

    .action-btn {
        padding: var(--space-xs) var(--space-md);
        border: 1px solid var(--accent-primary);
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--accent-primary);
        font-size: 0.8125rem;
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .action-btn:hover:not(:disabled) {
        background-color: var(--accent-primary);
        color: var(--bg-primary);
    }

    .action-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .upload-btn {
        display: flex;
        align-items: center;
        gap: var(--space-xs);
        padding: var(--space-xs) var(--space-md);
        border: 1px dashed var(--border-default);
        border-radius: var(--radius-sm);
        background-color: transparent;
        color: var(--text-secondary);
        font-size: 0.8125rem;
        cursor: pointer;
        transition: all var(--transition-fast);
    }

    .upload-btn:hover {
        border-color: var(--accent-primary);
        color: var(--accent-primary);
    }

    .upload-btn.dragover {
        border-color: var(--accent-primary);
        background-color: var(--accent-muted);
        color: var(--accent-primary);
    }

    .upload-icon {
        width: 14px;
        height: 14px;
    }

    .hidden-input {
        display: none;
    }

    .codemirror-wrapper {
        min-height: 240px;
        position: relative;
    }

    .codemirror-wrapper.dragover {
        outline: 2px dashed var(--accent-primary);
        outline-offset: -2px;
        background-color: var(--accent-muted);
    }

    .codemirror-wrapper :global(.cm-editor) {
        min-height: 240px;
    }

    .codemirror-wrapper :global(.cm-scroller) {
        overflow: auto;
    }

    .validation-error {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        padding: var(--space-sm) var(--space-md);
        background-color: rgba(255, 71, 87, 0.1);
        border-top: 1px solid var(--error);
    }

    .error-icon {
        width: 16px;
        height: 16px;
        color: var(--error);
        flex-shrink: 0;
    }

    .error-text {
        font-size: 0.8125rem;
        color: var(--error);
    }
</style>
