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

    // 隐藏通用加载器，改为流式加载器
    const loader = document.getElementById('chat-loader');
    if (loader) loader.style.display = 'none';

    // 创建 Agent 回答的容器
    const container = document.getElementById('chat-messages');
    const agentDiv = document.createElement('div');
    agentDiv.className = 'message-bubble message-agent';
    
    // 进度显示区域
    const progressDiv = document.createElement('div');
    progressDiv.className = 'streaming-progress';
    progressDiv.style.display = 'none';
    agentDiv.appendChild(progressDiv);

    // 内容显示区域
    const contentDiv = document.createElement('div');
    contentDiv.className = 'report-content';
    agentDiv.appendChild(contentDiv);
    
    container.appendChild(agentDiv);
    scrollToBottom();

    let fullAnswer = "";

    try {
        const formData = new FormData();
        formData.append('task_id', chatState.currentTaskId || `chat-${Date.now()}`);
        formData.append('asset_id', chatState.assetId);
        formData.append('question', apiQuestion);
        if (chatState.selectedImage) {
            formData.append('image', chatState.selectedImage);
        }

        const response = await fetch(`${api.baseURL}/v1/stream`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('流式请求失败');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // 留下最后可能不完整的一行

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = JSON.parse(line.slice(6));

                if (data.type === 'node_start') {
                    progressDiv.style.display = 'block';
                    const nodeNames = {
                        'planner': '正在思考规划...',
                        'executor': '正在执行检测工具...',
                        'consolidate': '正在整合多源信息...',
                        'answer': '正在生成诊断意见...'
                    };
                    progressDiv.innerHTML = `<div class="step-indicator active">${nodeNames[data.node] || data.node}</div>`;
                }
                else if (data.type === 'tool_start') {
                    progressDiv.innerHTML += `<div class="tool-indicator">➔ 调用工具: ${data.tool}</div>`;
                }
                else if (data.type === 'stream') {
                    if (data.subtype === 'thought') {
                        // 规划中的思考过程，显示在进度条下方
                        let thoughtDiv = progressDiv.querySelector('.thought-stream');
                        if (!thoughtDiv) {
                            thoughtDiv = document.createElement('div');
                            thoughtDiv.className = 'thought-stream';
                            progressDiv.appendChild(thoughtDiv);
                        }
                        thoughtDiv.textContent += data.content;
                    }
                    else {
                        // 最终回答内容
                        fullAnswer += data.content;
                        if (typeof renderMarkdownLite === 'function') {
                            contentDiv.innerHTML = renderMarkdownLite(fullAnswer);
                        } else {
                            contentDiv.textContent = fullAnswer;
                        }
                    }
                }
                else if (data.type === 'error') {
                    throw new Error(data.message || "后端执行流出错");
                }
                else if (data.type === 'final_result') {
                    chatState.currentTaskId = data.task_id;
                    progressDiv.style.display = 'none';
                }
                
                scrollToBottom();
            }
        }

        // 交互清理
        chatState.selectedImage = null;
        document.getElementById('image-preview-area').style.display = 'none';

    } catch (error) {
        console.error('Streaming error:', error);
        contentDiv.innerHTML = `<div style="color: #ef4444;">抱歉，处理您的请求时发生了错误：${error.message}</div>`;
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

/**
 * 极简 Markdown 渲染（支持标题、加粗、列表）
 */
function renderMarkdownLite(text) {
    if (!text) return "";
    let html = text
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
        .replace(/^\- (.*$)/gim, '<li>$1</li>')
        .replace(/\n/gim, '<br>');
    
    // 简单的列表包装
    if (html.includes('<li>')) {
        html = html.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');
    }
    
    return html;
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
