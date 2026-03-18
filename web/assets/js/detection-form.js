/**
 * Detection Form Module
 * Handles detection task form submission and result display
 */

let formState = {
    isLoading: false,
    currentResult: null,
    previewUrl: null,
};

/**
 * Initialize form on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing detection form...');
    
    setupFormListeners();
    autofillTaskId();
});

/**
 * Auto-fill task ID with unique value
 */
function autofillTaskId() {
    const taskIdInput = document.getElementById('task-id');
    if (taskIdInput && !taskIdInput.value) {
        taskIdInput.value = generateTaskId();
    }
}

/**
 * Setup form event listeners
 */
function setupFormListeners() {
    const form = document.getElementById('detection-form');
    const imageInput = document.getElementById('image-input');

    // Form submission
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }

    if (imageInput) {
        imageInput.addEventListener('change', () => {
            const file = imageInput.files?.[0] || null;
            updateImagePreview(file);
        });
    }
}

function updateImagePreview(file) {
    const container = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('image-preview');
    const previewMeta = document.getElementById('image-preview-meta');

    if (!container || !previewImage) {
        return;
    }

    if (!file) {
        clearImagePreview();
        return;
    }

    if (!file.type || !file.type.startsWith('image/')) {
        clearImagePreview();
        const imageInput = document.getElementById('image-input');
        if (imageInput) {
            imageInput.value = '';
        }
        showError('Please upload a valid image file');
        return;
    }

    if (formState.previewUrl) {
        window.URL.revokeObjectURL(formState.previewUrl);
        formState.previewUrl = null;
    }

    const url = window.URL.createObjectURL(file);
    formState.previewUrl = url;
    previewImage.src = url;
    previewImage.alt = file.name || 'Uploaded image';
    container.classList.add('show');

    if (previewMeta) {
        previewMeta.textContent = `${file.name || 'image'} · ${formatFileSize(file.size)}`;
    }
}

function clearImagePreview() {
    const container = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('image-preview');
    const previewMeta = document.getElementById('image-preview-meta');

    if (formState.previewUrl) {
        window.URL.revokeObjectURL(formState.previewUrl);
        formState.previewUrl = null;
    }

    if (previewImage) {
        previewImage.removeAttribute('src');
    }

    if (previewMeta) {
        previewMeta.textContent = '';
    }

    if (container) {
        container.classList.remove('show');
    }
}

function formatFileSize(bytes) {
    if (!Number.isFinite(bytes)) {
        return '-';
    }

    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
    }

    const precision = size >= 10 || unitIndex === 0 ? 0 : 1;
    return `${size.toFixed(precision)} ${units[unitIndex]}`;
}

/**
 * Handle form submission
 */
async function handleFormSubmit(e) {
    e.preventDefault();

    // Validate form
    if (!validateForm()) {
        return;
    }

    // Get form data
    const taskData = getFormData();

    // Show loading state
    showLoading(true);

    try {
        // Submit detection task
        console.log('Submitting detection task:', taskData);
        const result = await apiClient.runDetection(taskData);

        // Store result
        formState.currentResult = result;

        // Display result
        displayResult(result);

        // Add to recent detections if dashboard script is loaded
        if (typeof addRecentDetection === 'function') {
            const detection = {
                task_id: result.task_id,
                asset_id: document.getElementById('asset-id')?.value?.trim() || '',
                status: result.status,
                anomalies: result.anomalies || [],
                summary: result.summary,
                metadata: result.metadata,
            };
            addRecentDetection(detection);
        }

        showToast('Detection completed successfully!', 'success');
    } catch (error) {
        console.error('Detection failed:', error);
        showError(error.message || 'Failed to run detection');
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

/**
 * Validate form inputs
 */
function validateForm() {
    const taskId = document.getElementById('task-id').value.trim();
    const assetId = document.getElementById('asset-id').value.trim();
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;
    const imageFile = document.getElementById('image-input')?.files?.[0];

    // Task ID
    if (!taskId) {
        showError('Task ID is required');
        return false;
    }

    // Asset ID
    if (!assetId) {
        showError('Asset ID is required');
        return false;
    }

    if (!imageFile) {
        showError('Please upload an image');
        return false;
    }

    // Time range
    if (!startTime || !endTime) {
        showError('Start time and end time are required');
        return false;
    }

    const start = new Date(startTime);
    const end = new Date(endTime);

    if (start >= end) {
        showError('Start time must be before end time');
        return false;
    }

    return true;
}

/**
 * Extract form data into request object
 */
function getFormData() {
    const taskId = document.getElementById('task-id').value.trim();
    const assetId = document.getElementById('asset-id').value.trim();
    const dataSource = document.getElementById('data-source').value || 'manual';
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;
    const question = document.getElementById('question-input')?.value?.trim() || '';
    const imageFile = document.getElementById('image-input')?.files?.[0];

    const formData = new FormData();
    formData.append('task_id', taskId);
    formData.append('asset_id', assetId);
    formData.append('start_time', formatDateTime(startTime));
    formData.append('end_time', formatDateTime(endTime));
    formData.append('data_source', dataSource);
    formData.append('question', question);
    formData.append('image', imageFile);

    const parameters = {
        tool_type: 'qwen3.5-plus',
        detector_params: {},
    };
    formData.append('parameters', JSON.stringify(parameters));
    return formData;
}

/**
 * Display detection results
 */
function displayResult(result) {
    const resultsSection = document.getElementById('results-section');
    const resultCard = document.getElementById('result-card');
    
    if (!resultsSection || !resultCard) {
        console.warn('Results section not found in DOM');
        return;
    }

    // Build result HTML
    const statusColor = result.status === 'success' ? '#16a34a' : '#dc2626';
    const statusText = result.status === 'success' ? '✓ Success' : '✗ Failed';

    resultCard.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="margin: 0;">Detection Results</h3>
            <span style="
                background: ${statusColor};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 0.9rem;
                font-weight: 500;
            ">${statusText}</span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
            <div style="background: #f8fafc; padding: 12px; border-radius: 6px;">
                <div style="font-size: 0.85rem; color: #666; margin-bottom: 4px;">Task ID</div>
                <div style="font-weight: 600; word-break: break-all;">${result.task_id}</div>
            </div>
            <div style="background: #f8fafc; padding: 12px; border-radius: 6px;">
                <div style="font-size: 0.85rem; color: #666; margin-bottom: 4px;">Anomalies Found</div>
                <div style="font-weight: 600; font-size: 1.5rem; color: ${result.anomalies && result.anomalies.length > 0 ? '#dc2626' : '#16a34a'};">
                    ${(result.anomalies || []).length}
                </div>
            </div>
            <div style="background: #f8fafc; padding: 12px; border-radius: 6px;">
                <div style="font-size: 0.85rem; color: #666; margin-bottom: 4px;">Completion Time</div>
                <div style="font-weight: 600;">${formatDateDisplay(new Date().toISOString())}</div>
            </div>
        </div>

        ${result.anomalies && result.anomalies.length > 0 ? `
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 12px 0;">Detected Anomalies</h4>
                <div class="anomalies-list">
                    ${result.anomalies.map((anomaly, index) => `
                        <div class="anomaly-item" style="
                            display: flex;
                            gap: 12px;
                            padding: 12px;
                            background: #fff;
                            border-left: 4px solid #dc2626;
                            border-radius: 4px;
                            margin-bottom: 8px;
                        ">
                            <div style="
                                min-width: 30px;
                                height: 30px;
                                background: #fecaca;
                                border-radius: 50%;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                color: #991b1b;
                                font-weight: bold;
                                font-size: 0.9rem;
                            ">${index + 1}</div>
                            <div style="flex: 1;">
                                <div style="font-weight: 600; margin-bottom: 4px;">
                                    ${anomaly.description || `Anomaly ${index + 1}`}
                                </div>
                                <div style="font-size: 0.9rem; color: #666;">
                                    Score: <span style="color: #dc2626; font-weight: 600;">
                                        ${(anomaly.score || 0).toFixed(3)}
                                    </span>
                                </div>
                                ${anomaly.details ? `
                                    <div style="font-size: 0.85rem; color: #666; margin-top: 4px;">
                                        ${anomaly.details}
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : `
            <div style="
                padding: 20px;
                background: #f0fdf4;
                border-left: 4px solid #16a34a;
                border-radius: 4px;
                margin-bottom: 20px;
            ">
                <div style="color: #166534; font-weight: 500;">✓ No anomalies detected</div>
            </div>
        `}

        ${result.summary ? `
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 8px 0;">Report</h4>
                <div class="report-md">${renderMarkdownLite(result.summary)}</div>
            </div>
        ` : ''}

        ${result.metadata ? `
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 8px 0;">Metadata</h4>
                <pre style="
                    background: white;
                    padding: 12px;
                    border-radius: 6px;
                    overflow-x: auto;
                    border: 1px solid #e2e8f0;
                    font-size: 0.85rem;
                    margin: 0;
                ">${JSON.stringify(result.metadata, null, 2)}</pre>
            </div>
        ` : ''}

        <div style="display: flex; gap: 10px; margin-top: 20px;">
            <button class="btn btn-primary" onclick="downloadResult()">Download Result</button>
            <button class="btn btn-secondary" onclick="resetForm()">New Detection</button>
        </div>
    `;

    // Show results section with animation
    resultsSection.style.display = 'block';
    resultsSection.style.animation = 'slideIn 0.3s ease';
    
    // Scroll to results
    setTimeout(() => {
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

/**
 * Show error message
 */
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';

        // Make it hard to miss when users are scrolled down.
        errorDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (typeof showToast === 'function') {
            showToast(message, 'error');
        }
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
}

/**
 * Show/hide loading overlay
 */
function showLoading(show) {
    formState.isLoading = show;
    
    const overlay = document.getElementById('loading-overlay');
    const submitBtn = document.querySelector('button[type="submit"]');

    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }

    if (submitBtn) {
        submitBtn.disabled = show;
        submitBtn.textContent = show ? 'Processing...' : 'Run Detection';
    }
}

/**
 * Reset form to initial state
 */
function resetForm() {
    const form = document.getElementById('detection-form');
    const resultsSection = document.getElementById('results-section');
    const errorDiv = document.getElementById('error-message');

    if (form) {
        form.reset();
        autofillTaskId();
    }

    if (resultsSection) {
        resultsSection.style.display = 'none';
    }

    if (errorDiv) {
        errorDiv.style.display = 'none';
    }

    clearImagePreview();

    // Reset threshold slider
    const thresholdSlider = document.getElementById('threshold-slider');
    if (thresholdSlider) {
        thresholdSlider.value = 0.5;
        updateThresholdDisplay(0.5);
    }

    formState.currentResult = null;

    // Scroll to form
    form?.scrollIntoView({ behavior: 'smooth' });
}

/**
 * Download result as JSON
 */
function downloadResult() {
    if (!formState.currentResult) {
        showToast('No result to download', 'info');
        return;
    }

    const json = JSON.stringify(formState.currentResult, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detection-result-${formState.currentResult.task_id}.json`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

    showToast('Result downloaded successfully', 'success');
}

/**
 * Navigate to dashboard
 */
function goToDashboard() {
    window.location.href = 'index.html';
}
