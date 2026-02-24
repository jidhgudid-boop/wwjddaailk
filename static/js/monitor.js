// 监控面板 JavaScript

// 全局变量
let redisLatencyChart = null;
let connectionsChart = null;
let trafficSpeedChart = null;
let latencyHistory = [];
let sessionsHistory = [];
let usersHistory = [];
let trafficSpeedHistory = [];
let activeTransfersHistory = [];
const maxHistoryLength = 60;  // 增加到60个数据点（5分钟历史）

// XSS 防护：HTML 转义函数
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// 复制到剪贴板功能
async function copyToClipboard(text, button) {
    try {
        await navigator.clipboard.writeText(text);
        // 显示复制成功反馈
        const originalText = button.textContent;
        button.textContent = '✓';
        button.classList.add('copy-success');
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('copy-success');
        }, 1500);
    } catch (err) {
        console.error('复制失败:', err);
        // 回退方案：使用传统的复制方法
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            button.textContent = '✓';
            button.classList.add('copy-success');
            setTimeout(() => {
                button.textContent = '📋';
                button.classList.remove('copy-success');
            }, 1500);
        } catch (e) {
            console.error('回退复制也失败:', e);
        }
        document.body.removeChild(textarea);
    }
}

// 初始化图表
function initCharts() {
    // Redis延迟图表
    const redisCtx = document.getElementById('redisLatencyChart').getContext('2d');
    redisLatencyChart = new Chart(redisCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Redis延迟 (ms)',
                data: [],
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '延迟 (ms)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '时间'
                    }
                }
            }
        }
    });
    
    // 活跃连接图表
    const connectionsCtx = document.getElementById('connectionsChart').getContext('2d');
    connectionsChart = new Chart(connectionsCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: '活跃会话',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: '活跃用户',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '连接数'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '时间'
                    }
                }
            }
        }
    });
    
    // 流量速度趋势图表
    const trafficSpeedCtx = document.getElementById('trafficSpeedChart').getContext('2d');
    trafficSpeedChart = new Chart(trafficSpeedCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: '总传输速度 (Mbps)',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: '活跃传输数',
                    data: [],
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '速度 (Mbps)'
                    },
                    position: 'left'
                },
                y1: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: '传输数'
                    },
                    position: 'right',
                    grid: {
                        drawOnChartArea: false
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: '时间'
                    }
                }
            }
        }
    });
}

// 更新图表数据
function updateCharts(healthData, statsData, transfersData) {
    const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    // 更新Redis延迟
    if (healthData && healthData.redis && healthData.redis.latency_ms !== undefined) {
        latencyHistory.push(healthData.redis.latency_ms);
        if (latencyHistory.length > maxHistoryLength) {
            latencyHistory.shift();
        }
        
        redisLatencyChart.data.labels.push(now);
        if (redisLatencyChart.data.labels.length > maxHistoryLength) {
            redisLatencyChart.data.labels.shift();
        }
        
        redisLatencyChart.data.datasets[0].data = latencyHistory;
        redisLatencyChart.update('none');
    }
    
    // 更新活跃连接
    if (statsData && statsData.redis_stats) {
        const activeSessions = statsData.redis_stats.active_sessions || 0;
        const activeUsers = statsData.redis_stats.active_users || 0;
        
        sessionsHistory.push(activeSessions);
        usersHistory.push(activeUsers);
        
        if (sessionsHistory.length > maxHistoryLength) {
            sessionsHistory.shift();
            usersHistory.shift();
        }
        
        if (connectionsChart.data.labels.length === 0 || connectionsChart.data.labels[connectionsChart.data.labels.length - 1] !== now) {
            connectionsChart.data.labels.push(now);
            if (connectionsChart.data.labels.length > maxHistoryLength) {
                connectionsChart.data.labels.shift();
            }
        }
        
        connectionsChart.data.datasets[0].data = sessionsHistory;
        connectionsChart.data.datasets[1].data = usersHistory;
        connectionsChart.update('none');
    }
    
    // 更新流量速度趋势
    const transferSpeed = (transfersData && transfersData.total_speed_mbps) ? transfersData.total_speed_mbps : 0;
    const activeTransfers = (transfersData && transfersData.active_transfers) ? transfersData.active_transfers : 0;
    
    trafficSpeedHistory.push(transferSpeed);
    activeTransfersHistory.push(activeTransfers);
    
    if (trafficSpeedHistory.length > maxHistoryLength) {
        trafficSpeedHistory.shift();
        activeTransfersHistory.shift();
    }
    
    // 添加时间标签（避免重复）
    const lastLabel = trafficSpeedChart.data.labels.length > 0 
        ? trafficSpeedChart.data.labels[trafficSpeedChart.data.labels.length - 1] 
        : null;
    if (lastLabel !== now) {
        trafficSpeedChart.data.labels.push(now);
        if (trafficSpeedChart.data.labels.length > maxHistoryLength) {
            trafficSpeedChart.data.labels.shift();
        }
    }
    
    trafficSpeedChart.data.datasets[0].data = trafficSpeedHistory;
    trafficSpeedChart.data.datasets[1].data = activeTransfersHistory;
    trafficSpeedChart.update('none');
}

// 获取健康状态
async function fetchHealth() {
    const response = await fetch('/health');
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

// 获取统计信息
async function fetchStats() {
    const response = await fetch('/stats');
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

// 获取活跃传输
async function fetchActiveTransfers() {
    try {
        const response = await fetch('/active-transfers');
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取活跃传输失败:', error);
        return null;
    }
}

// 获取白名单信息
async function fetchWhitelistInfo() {
    try {
        const response = await fetch('/whitelist-info');
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取白名单信息失败:', error);
        return null;
    }
}

// 获取拒绝访问日志
async function fetchDeniedAccessLogs() {
    try {
        const response = await fetch('/api/access-logs/denied?limit=100');
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取拒绝访问日志失败:', error);
        return null;
    }
}

// 获取最近访问日志
async function fetchRecentAccessLogs() {
    try {
        const response = await fetch('/api/access-logs/recent?limit=100');
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取最近访问日志失败:', error);
        return null;
    }
}

// 获取Token重放日志
async function fetchReplayLogs() {
    try {
        const response = await fetch('/api/replay-logs?limit=300');
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取重放日志失败:', error);
        return null;
    }
}

// 创建信息项HTML
function createInfoItem(label, value, valueClass = '') {
    return `
        <div class="info-item">
            <span class="info-label">${label}</span>
            <span class="info-value ${valueClass}">${value}</span>
        </div>
    `;
}

// 格式化文件大小
function formatBytes(bytes) {
    if (bytes === 0 || bytes === null || bytes === undefined) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// 格式化速度
function formatSpeed(bytesPerSecond) {
    if (!bytesPerSecond || bytesPerSecond === 0) return '0 B/s';
    const mbps = bytesPerSecond / (1024 * 1024);
    if (mbps < 1) {
        const kbps = bytesPerSecond / 1024;
        return kbps.toFixed(2) + ' KB/s';
    }
    return mbps.toFixed(2) + ' MB/s';
}

// 格式化耗时
function formatElapsedTime(seconds) {
    if (!seconds || seconds === 0) return '0s';
    if (seconds < 60) {
        return seconds.toFixed(1) + 's';
    }
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}m ${secs}s`;
}

// 更新活跃传输显示
function updateActiveTransfers(transfersData) {
    if (!transfersData) {
        // 如果没有数据，显示0
        document.getElementById('active-transfer-count').textContent = '0';
        document.getElementById('total-transfer-speed').textContent = '0.00';
        document.getElementById('bandwidth-flow').textContent = '0.00';
        
        const transfersList = document.getElementById('transfers-list');
        transfersList.innerHTML = '<p class="no-transfers">当前没有活跃的传输</p>';
        return;
    }
    
    // 更新统计数据
    document.getElementById('active-transfer-count').textContent = 
        transfersData.active_transfers || 0;
    document.getElementById('total-transfer-speed').textContent = 
        transfersData.total_speed_mbps ? transfersData.total_speed_mbps.toFixed(2) : '0.00';
    
    // 更新全局带宽流速卡片
    const bandwidthFlow = transfersData.total_speed_mbps || 0;
    document.getElementById('bandwidth-flow').textContent = bandwidthFlow.toFixed(2);
    
    // 更新传输列表
    const transfersList = document.getElementById('transfers-list');
    
    if (!transfersData.transfers || transfersData.transfers.length === 0) {
        transfersList.innerHTML = '<p class="no-transfers">当前没有活跃的传输</p>';
        return;
    }
    
    // 生成传输项HTML
    let html = '';
    transfersData.transfers.forEach(transfer => {
        const progress = transfer.progress_percent || 0;
        const statusClass = {
            'active': 'status-active',
            'completed': 'status-completed',
            'error': 'status-error',
            'disconnected': 'status-disconnected'
        }[transfer.status] || '';
        
        const statusText = {
            'active': '传输中',
            'completed': '已完成',
            'error': '错误',
            'disconnected': '已断开'
        }[transfer.status] || transfer.status;
        
        html += `
            <div class="transfer-item ${statusClass}">
                <div class="transfer-header">
                    <span class="transfer-file" title="${transfer.full_path || transfer.file_path}">${transfer.file_path}</span>
                    <span class="transfer-status">${statusText}</span>
                </div>
                <div class="transfer-details">
                    ${transfer.uid ? '<span>👤 UID: ' + transfer.uid + '</span>' : ''}
                    <span>📁 ${transfer.file_type}</span>
                    <span>🌐 ${transfer.client_ip}</span>
                    <span>⚡ ${formatSpeed(transfer.speed_bps)}</span>
                    ${transfer.first_byte_latency_ms !== null && transfer.first_byte_latency_ms !== undefined ? '<span>⏱️ 首字节: ' + transfer.first_byte_latency_ms.toFixed(1) + 'ms</span>' : ''}
                    <span>📊 ${formatBytes(transfer.bytes_transferred)}${transfer.total_size ? ' / ' + formatBytes(transfer.total_size) : ''}</span>
                    ${transfer.elapsed ? '<span>⏲️ 耗时: ' + formatElapsedTime(transfer.elapsed) + '</span>' : ''}
                </div>
                ${transfer.full_path && transfer.full_path !== transfer.file_path ? '<div class="transfer-path">📂 ' + transfer.full_path + '</div>' : ''}
                ${transfer.progress_percent ? `
                <div class="transfer-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress.toFixed(1)}%"></div>
                    </div>
                    <span class="progress-text">${progress.toFixed(1)}%</span>
                </div>
                ` : ''}
            </div>
        `;
    });
    
    transfersList.innerHTML = html;
}

// 更新白名单列表显示
function updateWhitelistList(whitelistData) {
    const whitelistList = document.getElementById('whitelist-list');
    
    if (!whitelistData || !whitelistData.entries || whitelistData.entries.length === 0) {
        whitelistList.innerHTML = '<p class="no-transfers">当前没有白名单条目</p>';
        return;
    }
    
    let html = '';
    whitelistData.entries.forEach(entry => {
        const ttlMinutes = Math.floor(entry.ttl_seconds / 60);
        const ttlSeconds = entry.ttl_seconds % 60;
        const ttlDisplay = ttlMinutes > 0 ? `${ttlMinutes}分${ttlSeconds}秒` : `${ttlSeconds}秒`;
        
        const paths = entry.paths || [];
        const pathsHtml = paths.map(p => `<span class="path-badge">${p.key_path}</span>`).join(' ');
        
        html += `
            <div class="whitelist-item">
                <div class="whitelist-header">
                    <span class="whitelist-uid">👤 UID: ${entry.uid || 'unknown'}</span>
                    <span class="whitelist-ttl">⏰ 剩余: ${ttlDisplay}</span>
                </div>
                <div class="whitelist-details">
                    <span>🌐 IP: ${entry.ip_patterns.join(', ')}</span>
                    <span>🔑 UA Hash: ${entry.ua_hash}</span>
                </div>
                <div class="whitelist-paths">
                    <span class="paths-label">📂 路径:</span>
                    ${pathsHtml || '<span class="path-badge">无</span>'}
                </div>
            </div>
        `;
    });
    
    whitelistList.innerHTML = html;
}

// 格式化时间戳
function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN');
}

// 截断长字符串
function truncateString(str, maxLength = 50) {
    if (!str) return '-';
    if (str.length <= maxLength) return str;
    return str.substring(0, maxLength) + '...';
}

// 更新拒绝访问日志显示
function updateDeniedAccessLogs(deniedData) {
    const tbody = document.getElementById('denied-logs-body');
    const totalElem = document.getElementById('denied-total');
    
    if (!deniedData || deniedData.status !== 'ok') {
        tbody.innerHTML = '<tr><td colspan="6" class="no-data">获取数据失败</td></tr>';
        totalElem.textContent = '-';
        return;
    }
    
    totalElem.textContent = deniedData.total || 0;
    
    if (!deniedData.records || deniedData.records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="no-data">暂无拒绝访问记录</td></tr>';
        return;
    }
    
    let html = '';
    deniedData.records.forEach(record => {
        html += `
            <tr>
                <td>${formatTimestamp(record.timestamp)}</td>
                <td>${escapeHtml(record.uid) || 'unknown'}</td>
                <td>${escapeHtml(record.ip) || '-'}</td>
                <td title="${escapeHtml(record.ua) || ''}">${escapeHtml(truncateString(record.ua, 30))}</td>
                <td title="${escapeHtml(record.path) || ''}">${escapeHtml(truncateString(record.path, 40))}</td>
                <td>${escapeHtml(record.reason) || '未知原因'}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 更新最近访问日志显示
function updateRecentAccessLogs(recentData) {
    const tbody = document.getElementById('recent-logs-body');
    const totalElem = document.getElementById('recent-total');
    
    if (!recentData || recentData.status !== 'ok') {
        tbody.innerHTML = '<tr><td colspan="5" class="no-data">获取数据失败</td></tr>';
        totalElem.textContent = '-';
        return;
    }
    
    totalElem.textContent = recentData.total || 0;
    
    if (!recentData.records || recentData.records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="no-data">暂无访问记录</td></tr>';
        return;
    }
    
    let html = '';
    recentData.records.forEach(record => {
        html += `
            <tr>
                <td>${formatTimestamp(record.timestamp)}</td>
                <td>${escapeHtml(record.uid) || 'unknown'}</td>
                <td>${escapeHtml(record.ip) || '-'}</td>
                <td title="${escapeHtml(record.ua) || ''}">${escapeHtml(truncateString(record.ua, 30))}</td>
                <td title="${escapeHtml(record.path) || ''}">${escapeHtml(truncateString(record.path, 50))}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 更新Token重放日志显示
function updateReplayLogs(replayData) {
    const tbody = document.getElementById('replay-logs-body');
    const totalElem = document.getElementById('replay-total');
    const blockedElem = document.getElementById('replay-blocked');
    
    if (!replayData || replayData.status !== 'ok') {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">获取数据失败</td></tr>';
        totalElem.textContent = '-';
        blockedElem.textContent = '-';
        return;
    }
    
    totalElem.textContent = replayData.total || 0;
    blockedElem.textContent = replayData.recent_blocked || 0;
    
    if (!replayData.records || replayData.records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">暂无重放日志记录</td></tr>';
        return;
    }
    
    let html = '';
    replayData.records.forEach((record, index) => {
        const statusClass = record.blocked ? 'status-blocked' : 'status-allowed';
        const statusText = record.blocked ? '🚫 已阻止' : '✅ 允许';
        
        // 使用 full_url（如果有）否则使用 path
        const displayPath = record.full_url || record.path || '-';
        const displayUa = record.ua || '-';
        
        // 为复制按钮创建唯一ID
        const pathBtnId = `copy-path-${index}`;
        const uaBtnId = `copy-ua-${index}`;
        
        html += `
            <tr class="${statusClass}">
                <td>${formatTimestamp(record.timestamp)}</td>
                <td>${escapeHtml(record.uid) || 'unknown'}</td>
                <td>${escapeHtml(record.ip) || '-'}</td>
                <td class="path-cell">
                    <div class="path-content" title="${escapeHtml(displayPath)}">
                        <span class="path-text">${escapeHtml(truncateString(displayPath, 60))}</span>
                        <button class="copy-btn" id="${pathBtnId}" data-copy="${escapeHtml(displayPath)}" onclick="copyToClipboard(this.dataset.copy, this)" title="复制完整路径">📋</button>
                    </div>
                </td>
                <td class="ua-cell">
                    <div class="ua-content" title="${escapeHtml(displayUa)}">
                        <span class="ua-text">${escapeHtml(truncateString(displayUa, 30))}</span>
                        <button class="copy-btn" id="${uaBtnId}" data-copy="${escapeHtml(displayUa)}" onclick="copyToClipboard(this.dataset.copy, this)" title="复制User Agent">📋</button>
                    </div>
                </td>
                <td>${record.count}/${record.max_uses}</td>
                <td>${statusText}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 获取Key访问日志
async function fetchKeyAccessLogs() {
    try {
        const response = await fetch('/api/key-access-logs?limit=300');
        if (!response.ok) {
            console.error('获取Key访问日志失败: HTTP', response.status);
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取Key访问日志失败:', error);
        return null;
    }
}

// 更新Key访问日志显示
function updateKeyAccessLogs(keyAccessData) {
    const tbody = document.getElementById('key-access-logs-body');
    const totalElem = document.getElementById('key-access-total');
    const blockedElem = document.getElementById('key-access-blocked');
    const exceededElem = document.getElementById('key-access-exceeded');
    
    if (!keyAccessData || keyAccessData.status !== 'ok') {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">获取数据失败</td></tr>';
        totalElem.textContent = '-';
        blockedElem.textContent = '-';
        exceededElem.textContent = '-';
        return;
    }
    
    totalElem.textContent = keyAccessData.total || 0;
    blockedElem.textContent = keyAccessData.recent_blocked || 0;
    exceededElem.textContent = keyAccessData.recent_max_exceeded || 0;
    
    if (!keyAccessData.records || keyAccessData.records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">暂无Key访问日志记录</td></tr>';
        return;
    }
    
    let html = '';
    keyAccessData.records.forEach((record, index) => {
        const statusClass = record.blocked ? 'status-blocked' : 'status-allowed';
        const statusText = record.blocked ? '🚫 已阻止' : '✅ 允许';
        
        const displayPath = record.path || '-';
        const displayUa = record.ua || '-';
        
        // 为复制按钮创建唯一ID
        const pathBtnId = `copy-key-path-${index}`;
        const uaBtnId = `copy-key-ua-${index}`;
        
        html += `
            <tr class="${statusClass}">
                <td>${formatTimestamp(record.timestamp)}</td>
                <td>${escapeHtml(record.uid) || 'unknown'}</td>
                <td>${escapeHtml(record.ip) || '-'}</td>
                <td class="path-cell">
                    <div class="path-content" title="${escapeHtml(displayPath)}">
                        <span class="path-text">${escapeHtml(truncateString(displayPath, 60))}</span>
                        <button class="copy-btn" id="${pathBtnId}" data-copy="${escapeHtml(displayPath)}" onclick="copyToClipboard(this.dataset.copy, this)" title="复制完整路径">📋</button>
                    </div>
                </td>
                <td class="ua-cell">
                    <div class="ua-content" title="${escapeHtml(displayUa)}">
                        <span class="ua-text">${escapeHtml(truncateString(displayUa, 30))}</span>
                        <button class="copy-btn" id="${uaBtnId}" data-copy="${escapeHtml(displayUa)}" onclick="copyToClipboard(this.dataset.copy, this)" title="复制User Agent">📋</button>
                    </div>
                </td>
                <td>${record.count}/${record.max_uses}</td>
                <td>${statusText}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 获取M3U8缓存统计
async function fetchM3u8CacheStats() {
    try {
        const response = await fetch('/api/m3u8-cache-stats');
        if (!response.ok) {
            console.error('获取M3U8缓存统计失败: HTTP', response.status);
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('获取M3U8缓存统计失败:', error);
        return null;
    }
}

// 更新M3U8缓存统计显示
function updateM3u8CacheStats(cacheData) {
    const tbody = document.getElementById('m3u8-cache-body');
    const countElem = document.getElementById('m3u8-cache-count');
    
    if (!cacheData || cacheData.status !== 'ok') {
        tbody.innerHTML = '<tr><td colspan="2" class="no-data">获取数据失败</td></tr>';
        countElem.textContent = '-';
        return;
    }
    
    countElem.textContent = cacheData.cache_count || 0;
    
    if (!cacheData.cache_details || cacheData.cache_details.length === 0) {
        tbody.innerHTML = '<tr><td colspan="2" class="no-data">暂无缓存记录</td></tr>';
        return;
    }
    
    let html = '';
    cacheData.cache_details.forEach((item) => {
        const ttlDisplay = item.ttl > 0 ? `${item.ttl}s` : '已过期';
        // Use TTL indicator with emoji instead of row background color
        const ttlIndicator = item.ttl > 300 ? '🟢' : (item.ttl > 0 ? '🟡' : '🔴');
        
        html += `
            <tr>
                <td title="完整哈希: ${escapeHtml(item.key_hash)}">${escapeHtml(truncateString(item.key_hash, 32))}</td>
                <td>${ttlIndicator} ${ttlDisplay}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 更新UI
function updateUI(healthData, statsData, transfersData, whitelistData) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display = 'none';
    document.getElementById('content').style.display = 'block';
    
    // 更新最后更新时间
    document.getElementById('last-update-time').textContent = new Date().toLocaleString('zh-CN');
    
    // 更新系统状态
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    if (healthData.status === 'healthy') {
        statusIndicator.className = 'status-indicator status-healthy';
        statusText.textContent = '健康';
    } else {
        statusIndicator.className = 'status-indicator status-unhealthy';
        statusText.textContent = '异常';
    }
    
    // 更新基本指标
    document.getElementById('redis-latency').textContent = 
        healthData.redis?.latency_ms !== undefined ? healthData.redis.latency_ms.toFixed(2) : '-';
    document.getElementById('worker-pid').textContent = healthData.worker_pid || '-';
    document.getElementById('traffic-status').textContent = 
        healthData.traffic_collector?.status || '-';
    
    // 更新统计数据
    if (statsData && statsData.redis_stats) {
        document.getElementById('active-sessions').textContent = 
            statsData.redis_stats.active_sessions !== 'N/A' ? statsData.redis_stats.active_sessions : '-';
        document.getElementById('active-users').textContent = 
            statsData.redis_stats.active_users !== 'N/A' ? statsData.redis_stats.active_users : '-';
        document.getElementById('m3u8-uses').textContent = 
            statsData.redis_stats.m3u8_single_uses !== 'N/A' ? statsData.redis_stats.m3u8_single_uses : '-';
        document.getElementById('ip-accesses').textContent = 
            statsData.redis_stats.ip_accesses !== 'N/A' ? statsData.redis_stats.ip_accesses : '-';
    }
    
    // 更新Redis信息
    const redisInfo = document.getElementById('redis-info');
    redisInfo.innerHTML = createInfoItem('状态', healthData.redis?.status || '-', 
        healthData.redis?.status === 'connected' ? 'success' : 'danger') +
        createInfoItem('延迟', (healthData.redis?.latency_ms !== undefined ? healthData.redis.latency_ms.toFixed(2) + ' ms' : '-'));
    
    // 更新HTTP客户端信息
    const httpInfo = document.getElementById('http-info');
    httpInfo.innerHTML = createInfoItem('状态', healthData.http_client?.status || '-',
        healthData.http_client?.status === 'active' ? 'success' : 'warning');
    
    // 更新流量收集器信息
    const trafficInfo = document.getElementById('traffic-info');
    trafficInfo.innerHTML = 
        createInfoItem('启用', healthData.traffic_collector?.enabled ? '是' : '否',
            healthData.traffic_collector?.enabled ? 'success' : '') +
        createInfoItem('状态', healthData.traffic_collector?.status || '-',
            healthData.traffic_collector?.status === 'running' ? 'success' : 'warning');
    
    // 更新系统信息
    const systemInfo = document.getElementById('system-info');
    systemInfo.innerHTML = 
        createInfoItem('进程ID', healthData.worker_pid || '-') +
        createInfoItem('时间戳', new Date(healthData.timestamp * 1000).toLocaleString('zh-CN')) +
        createInfoItem('Python版本', statsData?.system_info?.python_version?.split(' ')[0] || '-');
    
    // 更新性能配置
    if (healthData.config) {
        const perfConfig = document.getElementById('performance-config');
        perfConfig.innerHTML = 
            createInfoItem('流式传输', healthData.config.streaming_enabled ? '启用' : '禁用',
                healthData.config.streaming_enabled ? 'success' : '') +
            createInfoItem('并行验证', healthData.config.parallel_validation ? '启用' : '禁用',
                healthData.config.parallel_validation ? 'success' : '') +
            createInfoItem('Redis Pipeline', healthData.config.redis_pipeline ? '启用' : '禁用',
                healthData.config.redis_pipeline ? 'success' : '') +
            createInfoItem('请求去重', healthData.config.request_deduplication ? '启用' : '禁用',
                healthData.config.request_deduplication ? 'success' : '');
    }
    
    // 更新优化状态
    if (healthData.performance_optimization) {
        const optStatus = document.getElementById('optimization-status');
        optStatus.innerHTML = 
            createInfoItem('uvloop', healthData.performance_optimization.uvloop_enabled ? '启用' : '禁用',
                healthData.performance_optimization.uvloop_enabled ? 'success' : 'warning') +
            createInfoItem('优化器', healthData.performance_optimization.optimizer_enabled ? '启用' : '禁用',
                healthData.performance_optimization.optimizer_enabled ? 'success' : 'warning') +
            createInfoItem('优化级别', healthData.performance_optimization.optimization_level || '-');
    }
    
    // 更新活跃传输 (始终调用，即使数据为null也要显示0)
    updateActiveTransfers(transfersData);
    
    // 更新白名单列表
    if (whitelistData) {
        updateWhitelistList(whitelistData);
    }
    
    // 更新图表
    updateCharts(healthData, statsData, transfersData);
}

// 更新访问日志显示
function updateAccessLogs(deniedData, recentData, replayData, keyAccessData, m3u8CacheData) {
    if (deniedData) {
        updateDeniedAccessLogs(deniedData);
    }
    
    if (recentData) {
        updateRecentAccessLogs(recentData);
    }
    
    if (replayData) {
        updateReplayLogs(replayData);
    }
    
    if (keyAccessData) {
        updateKeyAccessLogs(keyAccessData);
    }
    
    if (m3u8CacheData) {
        updateM3u8CacheStats(m3u8CacheData);
    }
}

// 显示错误
function showError(message) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('content').style.display = 'none';
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = '❌ 错误: ' + message;
    errorDiv.style.display = 'block';
}

// 刷新数据
async function refreshData() {
    try {
        // 显示加载指示器（但不隐藏内容，如果已有数据）
        const contentDiv = document.getElementById('content');
        if (contentDiv.style.display === 'none') {
            document.getElementById('loading').style.display = 'block';
        }
        
        // 并行获取数据
        const [healthData, statsData, transfersData, whitelistData, deniedData, recentData, replayData, keyAccessData, m3u8CacheData] = await Promise.all([
            fetchHealth(),
            fetchStats(),
            fetchActiveTransfers(),
            fetchWhitelistInfo(),
            fetchDeniedAccessLogs(),
            fetchRecentAccessLogs(),
            fetchReplayLogs(),
            fetchKeyAccessLogs(),
            fetchM3u8CacheStats()
        ]);
        
        updateUI(healthData, statsData, transfersData, whitelistData);
        updateAccessLogs(deniedData, recentData, replayData, keyAccessData, m3u8CacheData);
    } catch (error) {
        console.error('获取数据失败:', error);
        showError(error.message);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
    refreshData();
    
    // 每5秒自动刷新（更频繁以显示实时传输）
    setInterval(refreshData, 5000);
});
