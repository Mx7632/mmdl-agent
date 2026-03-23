/**
 * RAG Console module
 */

document.addEventListener('DOMContentLoaded', () => {
    bindRagActions();
});

function bindRagActions() {
    const buildBtn = document.getElementById('build-btn');
    const queryBtn = document.getElementById('query-btn');
    const ingestBtn = document.getElementById('ingest-btn');

    if (buildBtn) buildBtn.addEventListener('click', onBuildRagIndex);
    if (queryBtn) queryBtn.addEventListener('click', onQueryRag);
    if (ingestBtn) ingestBtn.addEventListener('click', onIngestFeedback);
}

async function onBuildRagIndex() {
    const resultEl = document.getElementById('build-result');
    const datasetRoot = document.getElementById('dataset-root')?.value?.trim() || '';
    const includeNormal = !!document.getElementById('include-normal')?.checked;

    resultEl.textContent = '建库中，请稍候...';

    try {
        const res = await apiClient.ragBuild({
            dataset_root: datasetRoot || null,
            include_normal: includeNormal,
        });
        resultEl.textContent = JSON.stringify(res, null, 2);
        showToast('RAG 建库完成', 'success');
    } catch (error) {
        resultEl.textContent = `建库失败: ${error.message}`;
        showToast(`建库失败: ${error.message}`, 'error');
    }
}

async function onQueryRag() {
    const resultEl = document.getElementById('query-result');
    const contextEl = document.getElementById('query-context');

    const queryText = document.getElementById('query-text')?.value?.trim() || '';
    const category = document.getElementById('query-category')?.value?.trim() || '';
    const topK = Number(document.getElementById('query-topk')?.value || 5);

    if (!queryText) {
        showToast('请输入查询描述', 'error');
        return;
    }

    resultEl.textContent = '查询中...';
    contextEl.textContent = '生成上下文中...';

    try {
        const res = await apiClient.ragQuery({
            query_text: queryText,
            category: category || null,
            top_k: topK,
        });

        resultEl.textContent = JSON.stringify(res.results || [], null, 2);
        contextEl.textContent = res.prompt_context || '暂无上下文';
        showToast(`检索完成，共 ${res.count || 0} 条`, 'success');
    } catch (error) {
        resultEl.textContent = `查询失败: ${error.message}`;
        contextEl.textContent = '暂无上下文';
        showToast(`查询失败: ${error.message}`, 'error');
    }
}

async function onIngestFeedback() {
    const resultEl = document.getElementById('ingest-result');

    const imagePath = document.getElementById('feedback-image-path')?.value?.trim() || '';
    const category = document.getElementById('feedback-category')?.value?.trim() || 'unknown';
    const userDescription = document.getElementById('feedback-description')?.value?.trim() || '';
    const modelConfidence = Number(document.getElementById('feedback-confidence')?.value || 0);
    const anomalyType = document.getElementById('feedback-anomaly-type')?.value?.trim() || null;
    const severity = document.getElementById('feedback-severity')?.value || null;

    if (!imagePath || !userDescription) {
        showToast('图片路径和用户描述必填', 'error');
        return;
    }

    resultEl.textContent = '写入中...';

    try {
        const res = await apiClient.ragIngestFeedback({
            image_path: imagePath,
            category,
            user_description: userDescription,
            model_confidence: modelConfidence,
            is_anomaly: true,
            anomaly_type: anomalyType,
            severity,
        });
        resultEl.textContent = JSON.stringify(res, null, 2);
        showToast(res.message || '反馈写入完成', res.accepted ? 'success' : 'info');
    } catch (error) {
        resultEl.textContent = `反馈写入失败: ${error.message}`;
        showToast(`反馈写入失败: ${error.message}`, 'error');
    }
}
