/**
 * Simulation Configuration Form - Interactive Wireframe
 * This script demonstrates the UI interactions for the wireframe.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ===== 1. Simulink Model Upload =====
    setupModelUpload();

    // ===== 2. CSV Upload with Preview =====
    setupCSVUpload();

    // ===== 3. JSON Upload with Editor =====
    setupJSONUpload();

    // ===== 4. Form Submission =====
    setupFormSubmission();
});

// ===== Simulink Model Upload =====
function setupModelUpload() {
    const dropzone = document.getElementById('model-dropzone');
    const input = document.getElementById('model-input');
    const content = document.getElementById('model-content');
    const fileInfo = document.getElementById('model-file-info');
    const filename = document.getElementById('model-filename');
    const removeBtn = document.getElementById('model-remove');

    setupDragAndDrop(dropzone, (file) => {
        showModelFile(file);
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            showModelFile(e.target.files[0]);
        }
    });

    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        content.classList.remove('hidden');
        fileInfo.classList.add('hidden');
        dropzone.classList.remove('has-file');
        input.value = '';
    });

    function showModelFile(file) {
        filename.textContent = file.name;
        content.classList.add('hidden');
        fileInfo.classList.remove('hidden');
        dropzone.classList.add('has-file');
    }
}

// ===== CSV Upload with Preview =====
function setupCSVUpload() {
    const dropzone = document.getElementById('csv-dropzone');
    const input = document.getElementById('csv-input');
    const content = document.getElementById('csv-content');
    const preview = document.getElementById('csv-preview');
    const filenameSpan = document.getElementById('csv-filename');
    const replaceBtn = document.getElementById('csv-replace');
    const table = document.getElementById('csv-table');

    setupDragAndDrop(dropzone, (file) => {
        handleCSVFile(file);
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleCSVFile(e.target.files[0]);
        }
    });

    replaceBtn.addEventListener('click', () => {
        // Create a temporary input to select new file
        const tempInput = document.createElement('input');
        tempInput.type = 'file';
        tempInput.accept = '.csv';
        tempInput.onchange = (e) => {
            if (e.target.files.length > 0) {
                handleCSVFile(e.target.files[0]);
            }
        };
        tempInput.click();
    });

    function handleCSVFile(file) {
        filenameSpan.textContent = file.name;

        // Read and parse CSV
        const reader = new FileReader();
        reader.onload = (e) => {
            const csvData = parseCSV(e.target.result);
            renderCSVTable(csvData, table);

            // Update preview note
            const note = preview.querySelector('.preview-note');
            const totalRows = csvData.rows.length;
            const shownRows = Math.min(totalRows, 10);
            note.textContent = totalRows > 10
                ? `Showing first ${shownRows} rows of ${totalRows}`
                : `Showing all ${totalRows} rows`;
        };
        reader.readAsText(file);

        // Hide dropzone, show preview
        dropzone.classList.add('hidden');
        preview.classList.remove('hidden');
    }

    function parseCSV(text) {
        const lines = text.trim().split('\n');
        const headers = lines[0].split(',').map(h => h.trim());
        const rows = lines.slice(1).map(line =>
            line.split(',').map(cell => cell.trim())
        );
        return { headers, rows };
    }

    function renderCSVTable(data, tableEl) {
        // Render headers
        const thead = tableEl.querySelector('thead tr');
        thead.innerHTML = data.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('');

        // Render rows (max 10 for preview)
        const tbody = tableEl.querySelector('tbody');
        const rowsToShow = data.rows.slice(0, 10);
        tbody.innerHTML = rowsToShow.map(row =>
            `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`
        ).join('');
    }
}

// ===== JSON Upload with Editor =====
function setupJSONUpload() {
    const dropzone = document.getElementById('json-dropzone');
    const input = document.getElementById('json-input');
    const editorContainer = document.getElementById('json-editor-container');
    const filenameSpan = document.getElementById('json-filename');
    const textarea = document.getElementById('json-textarea');
    const status = document.getElementById('json-status');
    const errorDiv = document.getElementById('json-error');
    const prettifyBtn = document.getElementById('json-prettify');
    const replaceBtn = document.getElementById('json-replace');

    setupDragAndDrop(dropzone, (file) => {
        handleJSONFile(file);
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleJSONFile(e.target.files[0]);
        }
    });

    // Validate JSON on input
    textarea.addEventListener('input', () => {
        validateJSON(textarea.value);
    });

    // Prettify button
    prettifyBtn.addEventListener('click', () => {
        try {
            const parsed = JSON.parse(textarea.value);
            textarea.value = JSON.stringify(parsed, null, 2);
            validateJSON(textarea.value);
        } catch (e) {
            // Can't prettify invalid JSON
        }
    });

    // Replace button
    replaceBtn.addEventListener('click', () => {
        const tempInput = document.createElement('input');
        tempInput.type = 'file';
        tempInput.accept = '.json';
        tempInput.onchange = (e) => {
            if (e.target.files.length > 0) {
                handleJSONFile(e.target.files[0]);
            }
        };
        tempInput.click();
    });

    function handleJSONFile(file) {
        filenameSpan.textContent = file.name;

        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target.result;
            // Try to prettify on load
            try {
                const parsed = JSON.parse(content);
                textarea.value = JSON.stringify(parsed, null, 2);
            } catch {
                textarea.value = content;
            }
            validateJSON(textarea.value);
        };
        reader.readAsText(file);

        // Hide dropzone, show editor
        dropzone.classList.add('hidden');
        editorContainer.classList.remove('hidden');
    }

    function validateJSON(text) {
        try {
            JSON.parse(text);
            status.className = 'validation-status valid';
            status.innerHTML = `
                <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
                Valid JSON
            `;
            errorDiv.classList.add('hidden');
            return true;
        } catch (e) {
            status.className = 'validation-status invalid';
            status.innerHTML = `
                <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                Invalid JSON
            `;
            errorDiv.classList.remove('hidden');
            errorDiv.querySelector('.error-text').textContent = `Error: ${e.message}`;
            return false;
        }
    }
}

// ===== Form Submission =====
function setupFormSubmission() {
    const submitBtn = document.getElementById('submit-btn');

    submitBtn.addEventListener('click', () => {
        // Collect form data (for demo purposes)
        const formData = {
            model: document.getElementById('model-filename').textContent,
            csv: document.getElementById('csv-filename').textContent,
            config: document.getElementById('json-textarea').value,
            threshold: document.getElementById('threshold-input').value
        };

        console.log('Form submitted:', formData);

        // Visual feedback
        submitBtn.textContent = 'Submitting...';
        submitBtn.disabled = true;

        // Simulate API call
        setTimeout(() => {
            submitBtn.innerHTML = `
                <span>Run Simulation</span>
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
            `;
            submitBtn.disabled = false;
            alert('Simulation submitted! (This is a wireframe demo)');
        }, 1000);
    });
}

// ===== Utility Functions =====

function setupDragAndDrop(dropzone, onFileDrop) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => {
            dropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => {
            dropzone.classList.remove('dragover');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            onFileDrop(files[0]);
        }
    }, false);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
