/**
 * Expert Inspection Module
 * Handles expert-level industrial quality inspection task form submission and result display
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
    console.log('Initializing expert inspection system...');
    
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
    const dropZone = document.getElementById('drop-zone');

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

    // Drag and drop support
    if (dropZone && imageInput) {
        dropZone.addEventListener('click', () => imageInput.click());
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#2563eb';
            dropZone.style.background = '#eff6ff';
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.style.borderColor = '#cbd5e1';
            dropZone.style.background = '#f8fafc';
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#cbd5e1';
            dropZone.style.background = '#f8fafc';
            
            const file = e.dataTransfer.files?.[0];
            if (file) {
                imageInput.files = e.dataTransfer.files;
                updateImagePreview(file);
            }
        });
    }
}

function updateImagePreview(file) {
    const container = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('image-preview');
    const previewMeta = document.getElementById('image-preview-meta');

    if (!container || !previewImage) return;

    if (!file) {
        clearImagePreview();
        return;
    }

    if (!file.type || !file.type.startsWith('image/')) {
        clearImagePreview();
        showError('请上传有效的图像文件');
        return;
    }

    if (formState.previewUrl) {
        window.URL.revokeObjectURL(formState.previewUrl);
    }

    const url = window.URL.createObjectURL(file);
    formState.previewUrl = url;
    previewImage.src = url;
    container.style.display = 'block';

    if (previewMeta) {
        previewMeta.textContent = `${file.name} · ${formatFileSize(file.size)}`;
    }
}

function clearImagePreview() {
    const container = document.getElementById('image-preview-container');
    const previewImage = document.getElementById('image-preview');
    if (container) container.style.display = 'none';
    if (previewImage) previewImage.src = '';
    if (formState.previewUrl) {
        window.URL.revokeObjectURL(formState.previewUrl);
        formState.previewUrl = null;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Handle form submission
 */
async function handleFormSubmit(e) {
    e.preventDefault();

    const taskId = document.getElementById('task-id').value.trim();
    const assetId = document.getElementById('asset-id').value.trim();
    const category = document.getElementById('category-input').value;
    const imageFile = document.getElementById('image-input')?.files?.[0];

    if (!assetId || !imageFile) {
        showError('请完善资产编号和待检图像');
        return;
    }

    showLoading(true);

    try {
        const formData = new FormData();
        formData.append('task_id', taskId);
        formData.append('asset_id', assetId);
        formData.append('category', category);
        formData.append('start_time', new Date().toISOString());
        formData.append('end_time', new Date().toISOString());
        formData.append('data_source', 'expert_inspection');
        formData.append('question', document.getElementById('question-input')?.value?.trim() || '');
        formData.append('image', imageFile);
        
        const parameters = {
            tool_type: 'qwen3.5-plus',
            category: category
        };
        formData.append('parameters', JSON.stringify(parameters));

        console.log('开始专家质检任务...', taskId);
        const result = await apiClient.runDetection(formData);

        formState.currentResult = result;
        displayResult(result);
        
    } catch (error) {
        console.error('专家质检失败:', error);
        showError(error.message || '质检执行过程中发生错误');
    } finally {
        showLoading(false);
    }
}

/**
 * Display expert detection results
 */
function displayResult(result) {
    const resultsSection = document.getElementById('results-section');
    if (!resultsSection) return;

    // Set headers
    document.getElementById('result-task-id-header').textContent = `检测结论 - ${result.task_id}`;
    
    // Status Badge
    const statusBadge = document.getElementById('status-badge');
    const isAnomaly = result.status.toLowerCase() === 'anomaly';
    statusBadge.textContent = isAnomaly ? '发现异常 (Anomaly)' : '正常 (Normal)';
    statusBadge.className = `status-badge ${isAnomaly ? 'status-anomaly' : 'status-normal'}`;

    // Thought Chain
    document.getElementById('expert-thought').textContent = result.thought || '暂无推理过程。';

    // Detailed Findings (Explanation)
    const exp = result.explanation || {};
    document.getElementById('visual-evidence').textContent = exp.visual_evidence || '未提取到明显的视觉差异证据。';
    document.getElementById('standard-reference').textContent = exp.standard_reference || '基于通用工业标准。';
    document.getElementById('root-cause').textContent = exp.root_cause_analysis || '尚不明确，建议进一步排查。';
    
    // Confidence Score
    let scoreText = 'N/A';
    if (result.anomalies && result.anomalies.length > 0) {
        const maxScore = Math.max(...result.anomalies.map(a => a.score || 0));
        scoreText = (maxScore * 100).toFixed(1) + '%';
    } else if (isAnomaly) {
        scoreText = '高置信度';
    } else {
        scoreText = '100.0%';
    }
    document.getElementById('confidence-score').textContent = scoreText;

    // Action Recommendation
    document.getElementById('action-recommendation').textContent = exp.action_recommendation || '暂无明确建议。';

    // Markdown Summary
    const summaryEl = document.getElementById('report-summary');
    if (typeof renderMarkdownLite === 'function') {
        summaryEl.innerHTML = renderMarkdownLite(result.summary || '未生成报告摘要。');
    } else {
        summaryEl.textContent = result.summary || '未生成报告摘要。';
    }

    resultsSection.style.display = 'block';
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function showLoading(show) {
    formState.isLoading = show;
    const overlay = document.getElementById('loading-overlay');
    const submitBtn = document.querySelector('button[type="submit"]');

    if (overlay) overlay.style.display = show ? 'flex' : 'none';
    if (submitBtn) submitBtn.disabled = show;
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => { errorDiv.style.display = 'none'; }, 5000);
    }
}

function resetForm() {
    const form = document.getElementById('detection-form');
    if (form) form.reset();
    autofillTaskId();
    clearImagePreview();
    document.getElementById('results-section').style.display = 'none';
}

function downloadReport() {
    if (!formState.currentResult) return;
    const data = JSON.stringify(formState.currentResult, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `expert-report-${formState.currentResult.task_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

// Reuse helper from api-client.js or define here if missing
if (typeof generateTaskId !== 'function') {
    window.generateTaskId = () => `TASK-${Date.now()}-${Math.random().toString(36).substr(2, 5).toUpperCase()}`;
}
