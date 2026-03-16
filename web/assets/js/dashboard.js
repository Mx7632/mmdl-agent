/**
 * Dashboard Module
 * Handles dashboard page interactions and data display
 */

let dashboardState = {
    stats: {
        recentTasks: 0,
        anomaliesFound: 0,
        successRate: '0%',
    },
    recentDetections: [],
    systemHealth: 'unknown', // online, offline, loading
};

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Initializing dashboard...');
    
    await loadSystemStatus();
    await loadRecentDetections();
    setupEventListeners();
    startHealthCheckInterval();
});

/**
 * Load and display system status
 */
async function loadSystemStatus() {
    const statusBadge = document.getElementById('system-status');
    
    if (!statusBadge) return;

    try {
        statusBadge.textContent = 'Loading...';
        statusBadge.className = 'status-badge loading';

        // /health has been removed; use lightweight root probe instead.
        await apiClient.getAppInfo();
        
        dashboardState.systemHealth = 'online';
        statusBadge.textContent = '🟢 Online';
        statusBadge.className = 'status-badge online';
    } catch (error) {
        console.error('Health check failed:', error);
        dashboardState.systemHealth = 'offline';
        const statusBadge = document.getElementById('system-status');
        if (statusBadge) {
            statusBadge.textContent = '🔴 Offline';
            statusBadge.className = 'status-badge offline';
        }
    }
}

/**
 * Load recent detections from localStorage or API
 */
async function loadRecentDetections() {
    // Try to load from localStorage first
    const stored = localStorage.getItem('recentDetections');
    if (stored) {
        try {
            dashboardState.recentDetections = JSON.parse(stored).slice(0, 5);
            updateDetectionsList();
        } catch (e) {
            console.warn('Failed to parse stored detections');
        }
    }
}

/**
 * Update detection statistics
 */
function updateStatistics() {
    const detections = dashboardState.recentDetections;

    // Calculate recent tasks count
    dashboardState.stats.recentTasks = detections.length;

    // Calculate anomalies found
    dashboardState.stats.anomaliesFound = detections.reduce((sum, d) => {
        return sum + (d.anomalies ? d.anomalies.length : 0);
    }, 0);

    // Calculate success rate
    const successful = detections.filter(d => d.status === 'success').length;
    const total = detections.length || 1;
    dashboardState.stats.successRate = Math.round((successful / total) * 100) + '%';

    // Update DOM
    const statElements = {
        'recent-tasks-count': dashboardState.stats.recentTasks,
        'anomalies-count': dashboardState.stats.anomaliesFound,
        'success-rate-count': dashboardState.stats.successRate,
    };

    Object.entries(statElements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });
}

/**
 * Update recent detections list
 */
function updateDetectionsList() {
    const list = document.getElementById('recent-list');
    
    if (!list) return;

    if (dashboardState.recentDetections.length === 0) {
        list.innerHTML = '<p style="color: #888; padding: 20px; text-align: center;">No detections yet. <a href="detection.html">Start a new detection task</a></p>';
        updateStatistics();
        return;
    }

    list.innerHTML = dashboardState.recentDetections
        .map((detection, index) => `
            <div class="detection-item">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <h4 style="margin: 0 0 8px 0;">${detection.task_id}</h4>
                        <p style="margin: 0 0 10px 0; color: #666; font-size: 0.9rem;">
                            Asset: ${detection.asset_id || 'N/A'} | 
                            ${formatDateDisplay(detection.created_at || new Date().toISOString())}
                        </p>
                    </div>
                    <span class="detection-status ${detection.status}">
                        ${detection.status === 'success' ? '✓ Success' : detection.status === 'failed' ? '✗ Failed' : '⏳ Pending'}
                    </span>
                </div>

                <div style="margin: 10px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9rem;">
                    <div><strong>Anomalies:</strong> ${(detection.anomalies || []).length}</div>
                    <div><strong>Summary:</strong> ${detection.summary || 'N/A'}</div>
                </div>

                <div style="display: flex; gap: 8px; margin-top: 10px;">
                    <button class="btn btn-secondary" onclick="viewDetectionDetails('${detection.task_id}', ${index})">
                        View Details
                    </button>
                    <button class="btn btn-outline" onclick="deleteDetection(${index})">
                        Delete
                    </button>
                </div>
            </div>
        `)
        .join('');

    updateStatistics();
}

/**
 * View detection details (modal or separate page)
 */
function viewDetectionDetails(taskId, index) {
    const detection = dashboardState.recentDetections[index];
    
    // Store in sessionStorage for detection detail page
    sessionStorage.setItem('selectedDetection', JSON.stringify(detection));
    
    // Show details in an expandable section (inline modal)
    const list = document.getElementById('recent-list');
    const items = list.querySelectorAll('.detection-item');
    
    if (items[index]) {
        const item = items[index];
        const details = item.querySelector('.detection-details');
        
        if (details) {
            details.remove();
        } else {
            const detailsDiv = document.createElement('div');
            detailsDiv.className = 'detection-details';
            detailsDiv.style.cssText = `
                margin-top: 15px;
                padding: 15px;
                background: #f8fafc;
                border-radius: 6px;
                border-left: 4px solid #2563eb;
            `;
            
            detailsDiv.innerHTML = `
                <h5 style="margin-top: 0;">Anomaly Details</h5>
                ${detection.anomalies && detection.anomalies.length > 0 ? `
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        ${detection.anomalies.map((anom, i) => `
                            <li style="margin: 8px 0; font-size: 0.9rem;">
                                ${anom.description || `Anomaly ${i + 1}`} 
                                (Score: ${(anom.score || 0).toFixed(3)})
                            </li>
                        `).join('')}
                    </ul>
                ` : '<p style="color: #888;">No anomalies detected</p>'}
                
                <h5>Summary</h5>
                <p style="margin: 10px 0; font-size: 0.9rem;">${detection.summary || 'No summary available'}</p>
                
                ${detection.metadata ? `
                    <h5>Metadata</h5>
                    <pre style="background: white; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 0.85rem;">
${JSON.stringify(detection.metadata, null, 2)}
                    </pre>
                ` : ''}
            `;
            
            item.appendChild(detailsDiv);
        }
    }
}

/**
 * Delete a detection from recent list
 */
function deleteDetection(index) {
    if (confirm('Delete this detection record?')) {
        dashboardState.recentDetections.splice(index, 1);
        localStorage.setItem('recentDetections', JSON.stringify(dashboardState.recentDetections));
        updateDetectionsList();
    }
}

/**
 * Setup event listeners for action buttons
 */
function setupEventListeners() {
    // Start New Detection button
    const startDetectionBtn = document.querySelector('[onclick*="window.location"]') || 
                              Array.from(document.querySelectorAll('button')).find(btn => 
                                  btn.textContent.includes('Start New Detection')
                              );
    
    if (startDetectionBtn && !startDetectionBtn.onclick) {
        startDetectionBtn.addEventListener('click', () => {
            window.location.href = 'detection.html';
        });
    }

    // View History button
    const viewHistoryBtn = Array.from(document.querySelectorAll('button')).find(btn => 
        btn.textContent.includes('View History')
    );
    
    if (viewHistoryBtn && !viewHistoryBtn.onclick) {
        viewHistoryBtn.addEventListener('click', () => {
            const list = document.getElementById('recent-list');
            if (list) {
                list.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }

    // Download Report button
    const downloadBtn = Array.from(document.querySelectorAll('button')).find(btn => 
        btn.textContent.includes('Download Report')
    );
    
    if (downloadBtn && !downloadBtn.onclick) {
        downloadBtn.addEventListener('click', downloadReport);
    }
}

/**
 * Start health check interval (every 30 seconds)
 */
function startHealthCheckInterval() {
    setInterval(loadSystemStatus, 30000);
}

/**
 * Download report as CSV
 */
function downloadReport() {
    const detections = dashboardState.recentDetections;
    
    if (detections.length === 0) {
        showToast('No detection data to download', 'info');
        return;
    }

    // Create CSV content
    const headers = ['Task ID', 'Asset ID', 'Status', 'Anomalies', 'Created At'];
    const rows = detections.map(d => [
        d.task_id,
        d.asset_id || '',
        d.status,
        (d.anomalies || []).length,
        d.created_at || '',
    ]);

    const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => 
            typeof cell === 'string' && cell.includes(',') ? `"${cell}"` : cell
        ).join(',')),
    ].join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detection-report-${new Date().getTime()}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

    showToast('Report downloaded successfully', 'success');
}

/**
 * Add a detection to recent list (called from detection.html)
 */
function addRecentDetection(detection) {
    // Add created_at timestamp
    detection.created_at = new Date().toISOString();

    // Add to front of list
    dashboardState.recentDetections.unshift(detection);

    // Keep only last 10
    dashboardState.recentDetections = dashboardState.recentDetections.slice(0, 10);

    // Save to localStorage
    localStorage.setItem('recentDetections', JSON.stringify(dashboardState.recentDetections));

    // Update display
    updateDetectionsList();
}
