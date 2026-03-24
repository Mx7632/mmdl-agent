/**
 * API Client Module
 * Handles all communication with the MMDL-Agent backend API
 */

class APIClient {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
        this.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        };
    }

    /**
     * Perform a generic fetch request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const isFormData = options.body && (
            (typeof FormData !== 'undefined' && options.body instanceof FormData) ||
            (typeof options.body.append === 'function' && typeof options.body.get === 'function')
        );
        const headers = { ...this.headers, ...(options.headers || {}) };
        if (isFormData) {
            delete headers['Content-Type'];
        }
        const config = {
            method: options.method || 'GET',
            headers,
            ...options,
        };

        if (options.body) {
            if (isFormData) {
                config.body = options.body;
            } else if (typeof options.body === 'object') {
                config.body = JSON.stringify(options.body);
            } else {
                config.body = options.body;
            }
        }

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({
                    message: response.statusText
                }));
                throw new Error(error.message || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * GET / - Get app info
     */
    async getAppInfo() {
        return this.request('/');
    }

    /**
     * POST /v1/detect - Run anomaly detection
     * @param {Object} task - Detection task data
     * @returns {Promise<Object>} Detection result
     */
    async runDetection(task) {
        return this.request('/v1/detect', {
            method: 'POST',
            body: task,
        });
    }

    /**
     * POST /v1/rag/build - Build vector index
     */
    async ragBuild(payload) {
        return this.request('/v1/rag/build', {
            method: 'POST',
            body: payload,
        });
    }

    /**
     * POST /v1/rag/build/start - Start async build job
     */
    async ragBuildStart(payload) {
        return this.request('/v1/rag/build/start', {
            method: 'POST',
            body: payload,
        });
    }

    /**
     * GET /v1/rag/build/status/{taskId} - Poll build status
     */
    async ragBuildStatus(taskId) {
        return this.request(`/v1/rag/build/status/${taskId}`);
    }

    /**
     * POST /v1/rag/query - Query similar cases
     */
    async ragQuery(payload) {
        return this.request('/v1/rag/query', {
            method: 'POST',
            body: payload,
        });
    }

    /**
     * POST /v1/rag/ingest-feedback - Ingest online feedback
     */
    async ragIngestFeedback(payload) {
        return this.request('/v1/rag/ingest-feedback', {
            method: 'POST',
            body: payload,
        });
    }
}

// Create global instance
const apiClient = new APIClient();

/**
 * Utility Functions
 */

/**
 * Parse data input (handles both CSV and JSON)
 */
function parseDataInput(input) {
    input = input.trim();
    
    // Try JSON array first
    if (input.startsWith('[')) {
        try {
            const parsed = JSON.parse(input);
            if (Array.isArray(parsed)) {
                return parsed.map(v => Number(v));
            }
        } catch (e) {
            // Fall through to CSV parsing
        }
    }

    // Parse as CSV
    return input.split(/[,\n]+/)
        .map(v => v.trim())
        .filter(v => v)
        .map(v => {
            const num = Number(v);
            if (isNaN(num)) {
                throw new Error(`Invalid number: ${v}`);
            }
            return num;
        });
}

/**
 * Format date for API (ISO 8601)
 */
function formatDateTime(dateTimeString) {
    if (!dateTimeString) return null;
    
    // For datetime-local input, append Z for UTC
    const date = new Date(dateTimeString);
    return date.toISOString();
}

/**
 * Format date for display
 */
function formatDateDisplay(isoString) {
    if (!isoString) return '-';
    
    const date = new Date(isoString);
    return date.toLocaleString();
}

/**
 * Generate a unique task ID
 */
function generateTaskId() {
    const now = new Date();
    const timestamp = now.getTime();
    const random = Math.random().toString(36).substr(2, 9);
    return `task-${timestamp}-${random}`;
}

/**
 * Render a safe subset of Markdown into HTML.
 * Supports: headings (#..###), bold (**), inline code (`), blockquote (>),
 * unordered/ordered lists, horizontal rule (---), and paragraphs.
 */
function renderMarkdownLite(markdown) {
    if (!markdown) return '';

    const escapeHtml = (s) => String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\"/g, '&quot;')
        .replace(/'/g, '&#39;');

    const formatInline = (s) => {
        // Inline code first to avoid formatting inside code spans.
        s = s.replace(/`([^`]+)`/g, (_m, p1) => `<code>${p1}</code>`);
        s = s.replace(/\*\*([^*]+)\*\*/g, (_m, p1) => `<strong>${p1}</strong>`);
        return s;
    };

    const lines = escapeHtml(markdown).split(/\r?\n/);
    const out = [];
    let inUl = false;
    let inOl = false;
    let inQuote = false;
    let seenH2 = false;

    const closeLists = () => {
        if (inUl) {
            out.push('</ul>');
            inUl = false;
        }
        if (inOl) {
            out.push('</ol>');
            inOl = false;
        }
    };

    const closeQuote = () => {
        if (inQuote) {
            out.push('</blockquote>');
            inQuote = false;
        }
    };

    for (const rawLine of lines) {
        const line = rawLine.trimRight();
        const trimmed = line.trim();

        if (!trimmed) {
            closeLists();
            closeQuote();
            continue;
        }

        if (/^---$/.test(trimmed)) {
            closeLists();
            closeQuote();
            out.push('<hr />');
            continue;
        }

        const headingMatch = /^(#{1,3})\s+(.*)$/.exec(trimmed);
        if (headingMatch) {
            closeLists();
            closeQuote();
            const level = headingMatch[1].length;
            let title = headingMatch[2];
            // Normalize headings like "2.异常详情" -> "2. 异常详情"
            title = title.replace(/^(\d{1,2})\.\s*(\S)/, '$1. $2');
            if (level === 2) {
                if (seenH2) out.push('<div class="report-section-divider"></div>');
                seenH2 = true;
            }
            out.push(`<h${level}>${formatInline(title)}</h${level}>`);
            continue;
        }

        const quoteMatch = /^&gt;\s?(.*)$/.exec(trimmed);
        if (quoteMatch) {
            closeLists();
            if (!inQuote) {
                out.push('<blockquote>');
                inQuote = true;
            }
            out.push(`<p>${formatInline(quoteMatch[1])}</p>`);
            continue;
        }

        const ulMatch = /^[-*]\s+(.*)$/.exec(trimmed);
        if (ulMatch) {
            closeQuote();
            if (inOl) {
                out.push('</ol>');
                inOl = false;
            }
            if (!inUl) {
                out.push('<ul>');
                inUl = true;
            }
            out.push(`<li>${formatInline(ulMatch[1])}</li>`);
            continue;
        }

        const olMatch = /^\d+\.\s+(.*)$/.exec(trimmed);
        if (olMatch) {
            closeQuote();
            if (inUl) {
                out.push('</ul>');
                inUl = false;
            }
            if (!inOl) {
                out.push('<ol>');
                inOl = true;
            }
            out.push(`<li>${formatInline(olMatch[1])}</li>`);
            continue;
        }

        closeLists();
        closeQuote();
        out.push(`<p>${formatInline(trimmed)}</p>`);
    }

    closeLists();
    closeQuote();
    return out.join('\n');
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#d1fae5' : type === 'error' ? '#fee2e2' : '#dbeafe'};
        color: ${type === 'success' ? '#065f46' : type === 'error' ? '#991b1b' : '#0c4a6e'};
        border-radius: 8px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        z-index: 2000;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Add CSS animation styles
 */
function initializeAnimations() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeAnimations);
