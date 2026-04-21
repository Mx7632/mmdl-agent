/**
 * Chat Module
 * Handles autonomous Q&A interaction
 */

const api = new APIClient(); // 使用封装好的 APIClient

let chatState = {
    selectedImage: null,
    isProcessing: false,
    currentTaskId: null, // 追踪当前任务 ID，支持多轮对话
    assetId: 'EQUIP-001' // 默认资产 ID
};

document.addEventListener('DOMContentLoaded', () => {
    setupChatListeners();
});

function setupChatListeners() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const uploadTrigger = document.getElementById('upload-trigger');
    const fileInput = document.getElementById('chat-image-input');
    const removeImgBtn = document.getElementById('remove-image');

    // Textarea auto-resize
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = (input.scrollHeight) + 'px';
    });

    // Send on Enter (but not Shift+Enter)
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleChatSubmit();
        }
    });

    sendBtn.addEventListener('click', handleChatSubmit);

    // Image Upload
    uploadTrigger.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleImageSelect(file);
    });

    removeImgBtn.addEventListener('click', () => {
        chatState.selectedImage = null;
        document.getElementById('image-preview-area').style.display = 'none';
        fileInput.value = '';
    });

    // Drag and Drop
    const chatMain = document.querySelector('.chat-main');
    chatMain.addEventListener('dragover', (e) => {
        e.preventDefault();
        chatMain.style.background = '#f1f5f9';
    });
    chatMain.addEventListener('dragleave', () => {
        chatMain.style.background = 'transparent';
    });
    chatMain.addEventListener('drop', (e) => {
        e.preventDefault();
        chatMain.style.background = 'transparent';
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) handleImageSelect(file);
    });
}

function handleImageSelect(file) {
    chatState.selectedImage = file;
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('chat-image-preview').src = e.target.result;
        document.getElementById('image-preview-area').style.display = 'block';
    };
    reader.readAsDataURL(file);
}

async function handleChatSubmit() {
    const input = document.getElementById('chat-input');
    let question = input.value.trim();
    
    if (!question && !chatState.selectedImage) return;
    if (chatState.isProcessing) return;

    const displayQuestion = question || (chatState.selectedImage ? "请分析这张图片中的工业异常情况。" : "");
    const apiQuestion = question || "请分析这张图片中的工业异常情况。";

    appendMessage('user', displayQuestion, chatState.selectedImage);
    
    input.value = '';
    input.style.height = 'auto';
    setProcessing(true);

    try {
        let result;
        
        // 如果是新任务（有图片，或者还没有 taskId）
        if (chatState.selectedImage || !chatState.currentTaskId) {
            const taskId = `chat-${Date.now()}`;
            const formData = new FormData();
            formData.append('task_id', taskId);
            formData.append('asset_id', chatState.assetId);
            formData.append('question', apiQuestion);
            formData.append('start_time', new Date(Date.now() - 3600000).toISOString());
            formData.append('end_time', new Date().toISOString());
            
            const category = document.getElementById('category-select').value;
            if (category) {
                formData.append('parameters', JSON.stringify({ category }));
            }
            
            if (chatState.selectedImage) {
                formData.append('image', chatState.selectedImage);
            }

            // 调用 detect_with_report 接口（支持 FormData）
            const response = await fetch(`${api.baseURL}/v1/detect_with_report`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.message || '检测任务启动失败');
            }
            result = await response.json();
            
            // 保存任务 ID 供后续对话
            chatState.currentTaskId = result.task_id;
            // 清除已发送的图片
            chatState.selectedImage = null;
            document.getElementById('image-preview-area').style.display = 'none';
        } 
        else {
            // 已有任务，进行多轮对话（使用 JSON）
            const response = await fetch(`${api.baseURL}/v1/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: chatState.currentTaskId,
                    question: apiQuestion
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.message || '对话请求失败');
            }
            result = await response.json();
        }
        
        appendAgentMessage(result);

    } catch (error) {
        console.error('Chat error:', error);
        appendMessage('agent', '抱歉，处理您的请求时发生了错误：' + error.message);
    } finally {
        setProcessing(false);
    }
}

function appendMessage(role, text, image = null) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message-bubble message-${role}`;
    
    if (image) {
        const img = document.createElement('img');
        img.className = 'message-image';
        img.src = URL.createObjectURL(image);
        div.appendChild(img);
    }
    
    if (text) {
        const p = document.createElement('div');
        p.textContent = text;
        div.appendChild(p);
    }
    
    container.appendChild(div);
    scrollToBottom();
}

function appendAgentMessage(result) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'message-bubble message-agent';
    
    // Final Answer (Markdown)
    const answerDiv = document.createElement('div');
    answerDiv.className = 'report-content';
    if (typeof renderMarkdownLite === 'function') {
        answerDiv.innerHTML = renderMarkdownLite(result.answer);
    } else {
        answerDiv.textContent = result.answer;
    }
    div.appendChild(answerDiv);

    // Steps Timeline
    if (result.steps && result.steps.length > 0) {
        const timeline = document.createElement('div');
        timeline.className = 'steps-timeline';
        timeline.innerHTML = '<div style="font-size: 0.75rem; font-weight: 700; margin-bottom: 8px; color: #94a3b8;">AGENT 推理步骤</div>';
        
        result.steps.forEach(step => {
            const item = document.createElement('div');
            item.className = 'step-item';
            item.innerHTML = `
                <div class="step-dot"></div>
                <div class="step-content">
                    <div class="step-name">${step.step_name}</div>
                    <div class="step-thought">${step.thought}</div>
                </div>
            `;
            timeline.appendChild(item);
        });
        div.appendChild(timeline);
    }
    
    container.appendChild(div);
    scrollToBottom();
}

function setProcessing(processing) {
    chatState.isProcessing = processing;
    const container = document.getElementById('chat-messages');
    
    if (processing) {
        const loader = document.createElement('div');
        loader.id = 'chat-loader';
        loader.className = 'message-bubble message-agent';
        loader.innerHTML = `
            <div class="typing-indicator">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
            <span style="font-size: 0.875rem; color: #64748b;">Agent 正在规划并分析中...</span>
        `;
        container.appendChild(loader);
    } else {
        const loader = document.getElementById('chat-loader');
        if (loader) loader.remove();
    }
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

function clearChat() {
    document.getElementById('chat-messages').innerHTML = `
        <div class="message-bubble message-agent">
            你好！我是 MMDL@NUAA 工业智能助手。您可以重新上传图片或提问。
        </div>
    `;
    chatState.currentTaskId = null;
    chatState.selectedImage = null;
    document.getElementById('image-preview-area').style.display = 'none';
    document.getElementById('chat-image-input').value = '';
}
