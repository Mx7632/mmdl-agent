/**
 * Chat Module
 * Handles autonomous Q&A interaction
 */

let chatState = {
    selectedImage: null,
    isProcessing: false
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
    
    // 如果没有文字也没有图片，则不提交
    if (!question && !chatState.selectedImage) return;
    
    if (chatState.isProcessing) return;

    // 如果只有图片没有文字，提供默认问题
    const displayQuestion = question || (chatState.selectedImage ? "请分析这张图片中的工业异常情况。" : "");
    const apiQuestion = question || "请分析这张图片中的工业异常情况。";

    // 1. Add User Message to UI
    appendMessage('user', displayQuestion, chatState.selectedImage);
    
    // 2. Clear input and show loading
    input.value = '';
    input.style.height = 'auto';
    setProcessing(true);

    try {
        // 3. Prepare Data
        const formData = new FormData();
        formData.append('question', apiQuestion);
        formData.append('task_id', `chat-${Date.now()}`);
        
        const category = document.getElementById('category-select').value;
        if (category) formData.append('category', category);
        
        if (chatState.selectedImage) {
            formData.append('image', chatState.selectedImage);
        }

        // 4. Call API
        const response = await fetch('http://localhost:8000/v1/chat', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('请求失败');
        
        const result = await response.json();
        
        // 5. Add Agent Message to UI
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
    const container = document.getElementById('chat-messages');
    container.innerHTML = `
        <div class="message-bubble message-agent">
            对话已清空。您可以重新上传图片或提问。
        </div>
    `;
}
