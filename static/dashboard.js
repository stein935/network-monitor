// Network Monitor Dashboard - Light Gruvbox Theme
// Single-page application with dynamic chart updates

let chart = null;
let ws = null;
let currentDate = null;
let currentHour = null;
let isCurrentHour = false;
let pollingInterval = null;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeChart();

    // If we have initial data, load it
    if (typeof INITIAL_DATE !== 'undefined' && typeof INITIAL_HOUR !== 'undefined') {
        currentDate = INITIAL_DATE;
        currentHour = INITIAL_HOUR;
        isCurrentHour = INITIAL_IS_CURRENT_HOUR;
        loadChartData(currentDate, currentHour);

        // Setup WebSocket for current hour
        if (isCurrentHour) {
            connectWebSocket();
        }
    }
});

// Initialize Chart.js
function initializeChart() {
    const ctx = document.getElementById('networkChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Response Time (ms)',
                    data: [],
                    borderColor: '#458588',
                    backgroundColor: 'rgba(69, 133, 136, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 4,
                    pointBackgroundColor: '#458588',
                    pointBorderColor: '#fbf1c7',
                    pointBorderWidth: 2,
                    yAxisID: 'y'
                },
                {
                    label: 'Success Rate (%)',
                    data: [],
                    borderColor: '#98971a',
                    backgroundColor: 'rgba(152, 151, 26, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 4,
                    pointBackgroundColor: [],
                    pointBorderColor: '#fbf1c7',
                    pointBorderWidth: 2,
                    yAxisID: 'y1',
                    segment: {
                        borderColor: ctx => {
                            const curr = ctx.p1.$context.parsed.y;
                            const prev = ctx.p0.$context.parsed.y;
                            return (curr < 100 || prev < 100) ? '#d65d0e' : '#98971a';
                        }
                    }
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: {
                    top: 10
                }
            },
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#3c3836',
                    titleColor: '#fbf1c7',
                    bodyColor: '#fbf1c7',
                    borderColor: '#7c6f64',
                    borderWidth: 1,
                    padding: 12,
                    titleFont: {
                        family: 'Fira Code',
                        size: 12
                    },
                    bodyFont: {
                        family: 'Fira Code',
                        size: 11
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(124, 111, 100, 0.2)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#504945',
                        font: {
                            family: 'Fira Code',
                            size: 11
                        },
                        maxRotation: 0,
                        minRotation: 0
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Response Time (ms)',
                        color: '#458588',
                        font: {
                            family: 'Fira Code',
                            size: 12,
                            weight: '500'
                        },
                        padding: {
                            bottom: 10
                        }
                    },
                    grid: {
                        color: 'rgba(124, 111, 100, 0.2)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#504945',
                        font: {
                            family: 'Fira Code',
                            size: 11
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Success Rate (%)',
                        color: '#98971a',
                        font: {
                            family: 'Fira Code',
                            size: 12,
                            weight: '500'
                        },
                        padding: {
                            bottom: 10
                        }
                    },
                    grid: {
                        drawOnChartArea: false,
                        drawBorder: false
                    },
                    ticks: {
                        color: '#504945',
                        font: {
                            family: 'Fira Code',
                            size: 11
                        },
                        stepSize: 5
                    },
                    min: 80,
                    max: 105
                }
            }
        }
    });
}

// Parse CSV data
function parseCSV(csv) {
    const lines = csv.trim().split('\n');
    if (lines.length === 0) return [];

    const headers = lines[0].split(',').map(h => h.trim());
    const data = [];

    for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',');
        const row = {};
        headers.forEach((header, index) => {
            row[header] = values[index] ? values[index].trim() : null;
        });
        data.push(row);
    }
    return data;
}

// Load chart data from server
function loadChartData(date, hour) {
    const csvUrl = `/csv/${date}/${hour}`;

    fetch(csvUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load data');
            }
            return response.text();
        })
        .then(csv => {
            updateChartWithData(csv);
        })
        .catch(error => {
            console.error('Error loading chart data:', error);
        });
}

// Update chart with CSV data
function updateChartWithData(csv) {
    const data = parseCSV(csv);

    if (data.length === 0) {
        console.warn('No data to display');
        return;
    }

    // Extract timestamps (HH:MM:SS only)
    const timestamps = data.map(row => {
        const ts = row.timestamp || '';
        const parts = ts.split(' ');
        return parts.length > 1 ? parts[1] : ts;
    });

    // Extract response times (handle nulls)
    const responseTimes = data.map(row => {
        const rt = row.response_time;
        return (rt === 'null' || rt === null || rt === '') ? null : parseFloat(rt);
    });

    // Calculate success rates
    const successRates = data.map(row => {
        const successCount = parseInt(row.success_count || 0);
        const totalCount = parseInt(row.total_count || 1);
        return (successCount / totalCount) * 100;
    });

    // Color-code success rate points
    const successColors = successRates.map(rate =>
        rate === 100 ? '#98971a' : '#d65d0e'
    );

    // Update chart
    chart.data.labels = timestamps;
    chart.data.datasets[0].data = responseTimes;
    chart.data.datasets[1].data = successRates;
    chart.data.datasets[1].pointBackgroundColor = successColors;

    // Auto-scale Y-axis for response time
    const validTimes = responseTimes.filter(t => t !== null);
    if (validTimes.length > 0) {
        const minTime = Math.min(...validTimes);
        const maxTime = Math.max(...validTimes);
        const padding = (maxTime - minTime) * 0.1 || 1;
        chart.options.scales.y.min = Math.max(0, minTime - padding);
        chart.options.scales.y.max = maxTime + padding;
    }

    chart.update();
}

// Load data when clicking a data item
function loadDataItem(date, hour, element) {
    // Remove active class from all items
    document.querySelectorAll('.data-item').forEach(item => {
        item.classList.remove('active');
    });

    // Add active class to clicked item
    element.classList.add('active');

    // Update current selection
    currentDate = date;
    currentHour = hour;

    // Update filename in header
    const dateFormatted = date.replace(/-/g, '');
    const filename = `monitor_${dateFormatted}_${String(hour).padStart(2, '0')}.csv`;
    document.querySelector('.file-name').textContent = filename;

    // Check if this is current hour
    const now = new Date();
    const currentDateStr = now.toISOString().split('T')[0];
    const currentHourNum = now.getHours();
    const wasCurrentHour = isCurrentHour;
    isCurrentHour = (date === currentDateStr && parseInt(hour) === currentHourNum);

    // Update live indicator
    const liveIndicator = document.querySelector('.live-indicator');
    if (isCurrentHour) {
        liveIndicator.style.display = 'flex';
    } else {
        liveIndicator.style.display = 'none';
    }

    // Disconnect WebSocket if leaving current hour
    if (wasCurrentHour && !isCurrentHour) {
        disconnectWebSocket();
    }

    // Connect WebSocket if entering current hour
    if (!wasCurrentHour && isCurrentHour) {
        connectWebSocket();
    }

    // Load chart data
    loadChartData(date, hour);

    // Update navigation buttons
    updateNavigationButtons();
}

// WebSocket connection
function connectWebSocket() {
    if (ws) return; // Already connected

    const wsUrl = `ws://${location.hostname}:8081`;
    updateWebSocketStatus('connecting');

    ws = new WebSocket(wsUrl);

    ws.onopen = function() {
        console.log('WebSocket connected');
        updateWebSocketStatus('connected');
        // Refresh chart on connection
        if (currentDate && currentHour) {
            loadChartData(currentDate, currentHour);
        }
    };

    ws.onmessage = function(event) {
        try {
            const message = JSON.parse(event.data);
            if (message.type === 'update' && currentDate && currentHour) {
                // Reload chart data
                loadChartData(currentDate, currentHour);
            }
        } catch (e) {
            console.error('WebSocket message error:', e);
        }
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateWebSocketStatus('disconnected');
        startPolling();
    };

    ws.onclose = function() {
        console.log('WebSocket closed');
        updateWebSocketStatus('disconnected');
        ws = null;
        startPolling();
    };
}

function disconnectWebSocket() {
    if (ws) {
        ws.close();
        ws = null;
    }
    stopPolling();
    updateWebSocketStatus('disconnected');
}

function updateWebSocketStatus(status) {
    const statusEl = document.querySelector('.websocket-status');
    if (!statusEl) return;

    statusEl.classList.remove('disconnected', 'connecting');

    if (status === 'connected') {
        statusEl.textContent = 'WebSocket: Connected';
        statusEl.style.background = '#98971a'; // green
    } else if (status === 'connecting') {
        statusEl.textContent = 'WebSocket: Connecting...';
        statusEl.classList.add('connecting');
    } else {
        statusEl.textContent = 'WebSocket: Disconnected (Polling)';
        statusEl.classList.add('disconnected');
    }
}

// HTTP polling fallback
function startPolling() {
    if (pollingInterval) return; // Already polling

    pollingInterval = setInterval(() => {
        if (document.visibilityState === 'visible' && currentDate && currentHour && isCurrentHour) {
            loadChartData(currentDate, currentHour);
        }
    }, 60000); // Poll every 60 seconds
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// Navigation functions
function goHome() {
    // Reload the page to reset to initial state
    window.location.href = '/';
}

function goPrevious() {
    const prevBtn = document.getElementById('prevBtn');
    if (prevBtn && !prevBtn.disabled) {
        const prevUrl = prevBtn.getAttribute('data-url');
        if (prevUrl) {
            navigateToDataItem(prevUrl);
        }
    }
}

function goNext() {
    const nextBtn = document.getElementById('nextBtn');
    if (nextBtn && !nextBtn.disabled) {
        const nextUrl = nextBtn.getAttribute('data-url');
        if (nextUrl) {
            navigateToDataItem(nextUrl);
        }
    }
}

function navigateToDataItem(url) {
    // Extract date and hour from URL: /view/YYYY-MM-DD/HH
    const match = url.match(/\/view\/([0-9-]+)\/(\d+)/);
    if (match) {
        const date = match[1];
        const hour = parseInt(match[2]);

        // Find the corresponding data item
        const dataItems = document.querySelectorAll('.data-item');
        for (let item of dataItems) {
            const itemDate = item.getAttribute('data-date');
            const itemHour = parseInt(item.getAttribute('data-hour'));
            if (itemDate === date && itemHour === hour) {
                item.click();
                item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                return;
            }
        }
    }
}

function updateNavigationButtons() {
    // Get all available data items
    const dataItems = Array.from(document.querySelectorAll('.data-item'));
    const activeItem = document.querySelector('.data-item.active');

    if (!activeItem || dataItems.length === 0) return;

    const activeIndex = dataItems.indexOf(activeItem);
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');

    // Previous button (index - 1)
    if (activeIndex > 0) {
        const prevItem = dataItems[activeIndex - 1];
        const prevDate = prevItem.getAttribute('data-date');
        const prevHour = prevItem.getAttribute('data-hour');
        prevBtn.disabled = false;
        prevBtn.setAttribute('data-url', `/view/${prevDate}/${prevHour}`);
    } else {
        prevBtn.disabled = true;
        prevBtn.setAttribute('data-url', '');
    }

    // Next button (index + 1)
    if (activeIndex < dataItems.length - 1) {
        const nextItem = dataItems[activeIndex + 1];
        const nextDate = nextItem.getAttribute('data-date');
        const nextHour = nextItem.getAttribute('data-hour');
        nextBtn.disabled = false;
        nextBtn.setAttribute('data-url', `/view/${nextDate}/${nextHour}`);
    } else {
        nextBtn.disabled = true;
        nextBtn.setAttribute('data-url', '');
    }
}
