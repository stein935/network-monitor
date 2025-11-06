// Network Monitor Dashboard - Light Gruvbox Theme
// Single-page application with dynamic chart updates

let chart = null;
let speedChart = null;
let ws = null;
let currentDate = null;
let currentHour = null;
let isCurrentHour = false;
let pollingInterval = null;
let speedTestPollingInterval = null;
let speedTestHoursOffset = 0; // 0 = current time (live), negative = hours back in time
let earliestSpeedTestTime = null; // Track earliest available data
let networkHoursOffset = 0; // 0 = current time (live), negative = hours back in time
let earliestNetworkTime = null; // Track earliest available data
let fetchInProgress = false; // Debounce flag for fetch requests
let speedFetchInProgress = false; // Debounce flag for speed test fetches

// Initialize dashboard on page load
document.addEventListener("DOMContentLoaded", function () {
  initializeChart();
  initializeSpeedTestChart();

  // Load network monitoring data (1 hour window)
  loadNetworkData();

  // Setup WebSocket for live data
  if (networkHoursOffset === 0) {
    connectWebSocket();
  }

  // Load speed test data
  loadSpeedTestData();
  startSpeedTestPolling();

  // Initialize Go Live button visibility
  updateNetworkGoLiveButton();
  updateSpeedGoLiveButton();
});

// Initialize Chart.js
function initializeChart() {
  const ctx = document.getElementById("networkChart").getContext("2d");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Response Time (ms)",
          data: [],
          borderColor: "#458588",
          backgroundColor: "rgba(69, 133, 136, 0.1)",
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 2,
          pointBackgroundColor: "#458588",
          pointBorderColor: "#fbf1c7",
          pointBorderWidth: 1,
          yAxisID: "y",
          fill: true,
        },
        {
          label: "Success Rate (%)",
          data: [],
          borderColor: "#98971a",
          backgroundColor: "rgba(152, 151, 26, 0.1)",
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 2,
          pointBackgroundColor: [],
          pointBorderColor: "#fbf1c7",
          pointBorderWidth: 1,
          yAxisID: "y1",
          fill: true,
          segment: {
            borderColor: (ctx) => {
              const curr = ctx.p1.$context.parsed.y;
              const prev = ctx.p0.$context.parsed.y;
              return curr < 100 || prev < 100 ? "#d65d0e" : "#98971a";
            },
          },
        },
      ],
    },
    options: {
      animation: false, // Disable animations for performance on Pi Zero
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: {
          top: 10,
        },
      },
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: "#3c3836",
          titleColor: "#fbf1c7",
          bodyColor: "#fbf1c7",
          borderColor: "#7c6f64",
          borderWidth: 1,
          padding: 12,
          titleFont: {
            family: "'Fira Code', monospace",
            size: 12,
          },
          bodyFont: {
            family: "'Fira Code', monospace",
            size: 11,
          },
        },
      },
      scales: {
        x: {
          grid: {
            color: "rgba(124, 111, 100, 0.2)",
            drawBorder: false,
          },
          ticks: {
            color: "#504945",
            font: {
              family: "'Fira Code', monospace",
              size: 11,
            },
            maxRotation: 0,
            minRotation: 0,
          },
        },
        y: {
          type: "linear",
          display: true,
          position: "left",
          title: {
            display: true,
            text: "Response Time (ms)",
            color: "#458588",
            font: {
              family: "'Fira Code', monospace",
              size: 12,
              weight: "500",
            },
            padding: {
              bottom: 10,
              top: 10,
            },
          },
          grid: {
            color: "rgba(124, 111, 100, 0.2)",
            drawBorder: false,
          },
          ticks: {
            color: "#504945",
            font: {
              family: "'Fira Code', monospace",
              size: 11,
            },
          },
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          title: {
            display: true,
            text: "Success Rate (%)",
            color: "#98971a",
            font: {
              family: "'Fira Code', monospace",
              size: 12,
              weight: "500",
            },
            padding: {
              bottom: 10,
              top: 10,
            },
          },
          grid: {
            drawOnChartArea: false,
            drawBorder: false,
          },
          ticks: {
            color: "#504945",
            font: {
              family: "'Fira Code', monospace",
              size: 11,
            },
            stepSize: 5,
          },
        },
      },
    },
  });
}

// Initialize Speed Test Chart
function initializeSpeedTestChart() {
  const speedCtx = document.getElementById("speedChart");
  if (!speedCtx) return; // Chart element might not exist yet

  speedChart = new Chart(speedCtx.getContext("2d"), {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Download (Mbps)",
          data: [],
          borderColor: "#458588",
          backgroundColor: "rgba(69, 133, 136, 0.1)",
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 2,
          pointBackgroundColor: "#458588",
          pointBorderColor: "#fbf1c7",
          pointBorderWidth: 1,
          yAxisID: "y",
          fill: true,
        },
        {
          label: "Upload (Mbps)",
          data: [],
          borderColor: "#b16286",
          backgroundColor: "rgba(177, 98, 134, 0.1)",
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 2,
          pointBackgroundColor: "#b16286",
          pointBorderColor: "#fbf1c7",
          pointBorderWidth: 1,
          yAxisID: "y1",
          fill: true,
        },
      ],
    },
    options: {
      animation: false, // Disable animations for performance on Pi Zero
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: {
          top: 10,
        },
      },
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          backgroundColor: "#3c3836",
          titleColor: "#fbf1c7",
          bodyColor: "#fbf1c7",
          borderColor: "#7c6f64",
          borderWidth: 1,
          padding: 12,
          titleFont: {
            family: "'Fira Code', monospace",
            size: 12,
          },
          bodyFont: {
            family: "'Fira Code', monospace",
            size: 11,
          },
        },
      },
      scales: {
        x: {
          grid: {
            color: "rgba(124, 111, 100, 0.2)",
            drawBorder: false,
          },
          ticks: {
            color: "#504945",
            font: {
              family: "'Fira Code', monospace",
              size: 11,
            },
            maxRotation: 0,
            minRotation: 0,
          },
        },
        y: {
          type: "linear",
          display: true,
          position: "left",
          title: {
            display: true,
            text: "Download (Mbps)",
            color: "#458588",
            font: {
              family: "'Fira Code', monospace",
              size: 12,
              weight: "500",
            },
            padding: {
              bottom: 10,
            },
          },
          grid: {
            color: "rgba(124, 111, 100, 0.2)",
            drawBorder: false,
          },
          ticks: {
            color: "#504945",
            font: {
              family: "'Fira Code', monospace",
              size: 11,
            },
          },
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          title: {
            display: true,
            text: "Upload (Mbps)",
            color: "#b16286",
            font: {
              family: "'Fira Code', monospace",
              size: 12,
              weight: "500",
            },
            padding: {
              bottom: 10,
            },
          },
          grid: {
            drawOnChartArea: false,
            drawBorder: false,
          },
          ticks: {
            color: "#504945",
            font: {
              family: "'Fira Code', monospace",
              size: 11,
            },
          },
        },
      },
    },
  });
}

// Load speed test data
function loadSpeedTestData() {
  // Debounce: prevent duplicate requests
  if (speedFetchInProgress) return;
  speedFetchInProgress = true;

  // Update date range display
  updateSpeedDateRange();

  // Calculate time range based on offset (12-hour window)
  const now = new Date();
  const endTime = new Date(
    now.getTime() + speedTestHoursOffset * 60 * 60 * 1000
  );
  const startTime = new Date(endTime.getTime() - 12 * 60 * 60 * 1000); // 12 hours before end

  // Format timestamps for API (YYYY-MM-DD HH:MM:SS) in UTC
  const formatTimestamp = (date) => {
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    const hours = String(date.getUTCHours()).padStart(2, "0");
    const minutes = String(date.getUTCMinutes()).padStart(2, "0");
    const seconds = String(date.getUTCSeconds()).padStart(2, "0");
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  };

  const startTimeStr = formatTimestamp(startTime);
  const endTimeStr = formatTimestamp(endTime);

  // Load both latest stats and recent tests in parallel
  const latestFetch = fetch("/api/speed-tests/latest")
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (data) {
        updateSpeedTestStats(data);
      }
    })
    .catch((error) => console.error("Error loading latest speed test:", error));

  const recentUrl = `/api/speed-tests/recent?start_time=${encodeURIComponent(
    startTimeStr
  )}&end_time=${encodeURIComponent(endTimeStr)}`;
  const recentFetch = fetch(recentUrl)
    .then((response) => (response.ok ? response.json() : []))
    .then((tests) => {
      updateSpeedTestChart(tests);
      updateSpeedNavButtons();
    })
    .catch((error) =>
      console.error("Error loading speed test history:", error)
    );

  // Wait for both fetches to complete before releasing debounce lock
  Promise.all([latestFetch, recentFetch]).finally(() => {
    speedFetchInProgress = false;
  });
}

// Update speed test stat cards
function updateSpeedTestStats(data) {
  const downloadEl = document.getElementById("speedDownload");
  const uploadEl = document.getElementById("speedUpload");
  const serverEl = document.getElementById("speedServer");
  const serverHostEl = document.getElementById("speedServerHost");
  const lastTestEl = document.getElementById("speedLastTest");
  const lastTestDateEl = document.getElementById("speedLastTestDate");

  if (downloadEl) downloadEl.textContent = data.download_mbps.toFixed(1);
  if (uploadEl) uploadEl.textContent = data.upload_mbps.toFixed(1);
  if (serverEl) serverEl.textContent = data.server_name || "Unknown";
  if (serverHostEl) {
    const serverHost = data.server_host || "";
    serverHostEl.textContent = serverHost;
    serverHostEl.title = serverHost; // Tooltip shows full URI on hover
  }

  if (lastTestEl && lastTestDateEl && data.timestamp) {
    const parts = data.timestamp.split(" ");
    if (parts.length === 2) {
      const timeParts = parts[1].split(":");
      lastTestEl.textContent = `${timeParts[0]}:${timeParts[1]}:${timeParts[2]}`;
      lastTestDateEl.textContent = parts[0];
    }
  }
}

// Update speed test chart
function updateSpeedTestChart(tests) {
  if (!speedChart || tests.length === 0) return;

  const labels = tests.map((test) => {
    const parts = test.timestamp.split(" ");
    if (parts.length > 1) {
      const timeParts = parts[1].split(":");
      return `${timeParts[0]}:${timeParts[1]}`;
    }
    return test.timestamp;
  });

  const downloads = tests.map((test) => test.download_mbps);
  const uploads = tests.map((test) => test.upload_mbps);

  speedChart.data.labels = labels;
  speedChart.data.datasets[0].data = downloads;
  speedChart.data.datasets[1].data = uploads;

  // Auto-scale axes
  if (downloads.length > 0) {
    const minDownload = Math.min(...downloads);
    const maxDownload = Math.max(...downloads);
    const downloadPadding = (maxDownload - minDownload) * 0.1 || 10;
    speedChart.options.scales.y.min = Math.max(
      0,
      minDownload - downloadPadding
    );
    speedChart.options.scales.y.max = maxDownload + downloadPadding;
  }

  if (uploads.length > 0) {
    const minUpload = Math.min(...uploads);
    const maxUpload = Math.max(...uploads);
    const uploadPadding = (maxUpload - minUpload) * 0.1 || 5;
    speedChart.options.scales.y1.min = Math.max(0, minUpload - uploadPadding);
    speedChart.options.scales.y1.max = maxUpload + uploadPadding;
  }

  speedChart.update("none"); // Use 'none' mode to skip animations for performance
}

// Start polling for speed test updates
function startSpeedTestPolling() {
  // Poll every 5 minutes for new speed tests (only when showing live data)
  // Use requestIdleCallback for lower priority, better performance
  speedTestPollingInterval = setInterval(() => {
    if (document.visibilityState === "visible" && speedTestHoursOffset === 0) {
      if ("requestIdleCallback" in window) {
        requestIdleCallback(() => loadSpeedTestData(), { timeout: 2000 });
      } else {
        loadSpeedTestData();
      }
    }
  }, 300000); // 5 minutes
}

// Update speed test navigation button states
function updateSpeedNavButtons() {
  const prevBtn = document.getElementById("speedPrevBtn");
  const nextBtn = document.getElementById("speedNextBtn");

  if (!prevBtn || !nextBtn) return;

  // Fetch earliest speed test to determine if we can go back further
  fetch("/api/speed-tests/earliest")
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (data && data.timestamp) {
        earliestSpeedTestTime = new Date(data.timestamp);

        // Disable prev button if the next window would end before earliest data
        const now = new Date();
        const currentEndTime = new Date(
          now.getTime() + speedTestHoursOffset * 60 * 60 * 1000
        );
        // Next window ends where current window starts (12 hours earlier)
        const nextWindowEndTime = new Date(
          currentEndTime.getTime() - 12 * 60 * 60 * 1000
        );

        // Disable if next window ends before earliest available data
        prevBtn.disabled =
          earliestSpeedTestTime && nextWindowEndTime < earliestSpeedTestTime;
      }
    })
    .catch((error) => {
      console.error("Error fetching earliest speed test:", error);
      prevBtn.disabled = false; // Allow navigation on error
    });

  // Disable next button if showing live data (offset = 0)
  nextBtn.disabled = speedTestHoursOffset === 0;
}

// Navigate to previous 12-hour window (older data)
function goSpeedPrevious() {
  speedTestHoursOffset -= 12; // Go back 12 hours
  loadSpeedTestData();
  updateSpeedGoLiveButton();
}

// Navigate to next 12-hour window (newer data)
function goSpeedNext() {
  speedTestHoursOffset += 12; // Go forward 12 hours
  if (speedTestHoursOffset > 0) {
    speedTestHoursOffset = 0; // Don't go beyond current time
  }
  loadSpeedTestData();
  updateSpeedGoLiveButton();
}

// Update network monitoring navigation button states
function updateNetworkNavButtons() {
  const prevBtn = document.getElementById("networkPrevBtn");
  const nextBtn = document.getElementById("networkNextBtn");

  if (!prevBtn || !nextBtn) return;

  // Fetch earliest log to determine if we can go back further
  fetch("/api/network-logs/earliest")
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (data && data.timestamp) {
        earliestNetworkTime = new Date(data.timestamp);

        // Disable prev button if we're at or beyond the earliest data
        const now = new Date();
        const currentEndTime = new Date(
          now.getTime() + networkHoursOffset * 60 * 60 * 1000
        );
        const nextStartTime = new Date(
          currentEndTime.getTime() - 2 * 60 * 60 * 1000
        ); // Would go back another 1 hour

        prevBtn.disabled =
          earliestNetworkTime && nextStartTime <= earliestNetworkTime;
      }
    })
    .catch((error) => {
      console.error("Error fetching earliest log:", error);
      prevBtn.disabled = false; // Allow navigation on error
    });

  // Disable next button if showing live data (offset = 0)
  nextBtn.disabled = networkHoursOffset === 0;
}

// Navigate to previous 1-hour window (older data)
function goNetworkPrevious() {
  networkHoursOffset -= 1; // Go back 1 hour

  // Disconnect WebSocket when leaving live view
  if (networkHoursOffset !== 0) {
    disconnectWebSocket();
  }

  loadNetworkData();
  updateNetworkGoLiveButton();
}

// Navigate to next 1-hour window (newer data)
function goNetworkNext() {
  networkHoursOffset += 1; // Go forward 1 hour
  if (networkHoursOffset > 0) {
    networkHoursOffset = 0; // Don't go beyond current time
  }

  // Reconnect WebSocket when returning to live view
  if (networkHoursOffset === 0) {
    connectWebSocket();
  }

  loadNetworkData();
  updateNetworkGoLiveButton();
}

// Go back to live view for network monitoring
function goNetworkLive() {
  networkHoursOffset = 0;

  // Reconnect WebSocket for live network data
  connectWebSocket();

  // Reload network data
  loadNetworkData();

  // Update button visibility
  updateNetworkGoLiveButton();
}

// Go back to live view for speed tests
function goSpeedLive() {
  speedTestHoursOffset = 0;

  // Reload speed test data
  loadSpeedTestData();

  // Update button visibility
  updateSpeedGoLiveButton();
}

// Update Network Go Live button visibility
function updateNetworkGoLiveButton() {
  const goLiveBtn = document.getElementById("networkGoLiveBtn");
  if (!goLiveBtn) return;

  // Show button only when not on live view
  if (networkHoursOffset === 0) {
    goLiveBtn.style.display = "none";
  } else {
    goLiveBtn.style.display = "flex";
  }
}

// Update Speed Test Go Live button visibility
function updateSpeedGoLiveButton() {
  const goLiveBtn = document.getElementById("speedGoLiveBtn");
  if (!goLiveBtn) return;

  // Show button only when not on live view
  if (speedTestHoursOffset === 0) {
    goLiveBtn.style.display = "none";
  } else {
    goLiveBtn.style.display = "flex";
  }
}

// Format date range display
function formatDateRange(startTime, endTime) {
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  const startMonth = months[startTime.getMonth()];
  const startDay = startTime.getDate();
  const startYear = startTime.getFullYear();
  const startHour = String(startTime.getHours()).padStart(2, "0");
  const startMin = String(startTime.getMinutes()).padStart(2, "0");

  const endMonth = months[endTime.getMonth()];
  const endDay = endTime.getDate();
  const endYear = endTime.getFullYear();
  const endHour = String(endTime.getHours()).padStart(2, "0");
  const endMin = String(endTime.getMinutes()).padStart(2, "0");

  // Check if same day
  if (startMonth === endMonth && startDay === endDay && startYear === endYear) {
    return `${startMonth} ${startDay}, ${startYear} ${startHour}:${startMin}  ${endHour}:${endMin}`;
  } else {
    return `${startMonth} ${startDay}, ${startYear} ${startHour}:${startMin}  ${endMonth} ${endDay}, ${endYear} ${endHour}:${endMin}`;
  }
}

// Update network date range display
function updateNetworkDateRange() {
  const now = new Date();
  const endTime = new Date(now.getTime() + networkHoursOffset * 60 * 60 * 1000);
  const startTime = new Date(endTime.getTime() - 1 * 60 * 60 * 1000); // 1 hour window

  const rangeEl = document.getElementById("networkDateRange");
  if (rangeEl) {
    rangeEl.textContent = formatDateRange(startTime, endTime);
  }
}

// Update speed test date range display
function updateSpeedDateRange() {
  const now = new Date();
  const endTime = new Date(
    now.getTime() + speedTestHoursOffset * 60 * 60 * 1000
  );
  const startTime = new Date(endTime.getTime() - 12 * 60 * 60 * 1000); // 12 hour window

  const rangeEl = document.getElementById("speedDateRange");
  if (rangeEl) {
    rangeEl.textContent = formatDateRange(startTime, endTime);
  }
}

// Parse CSV data
function parseCSV(csv) {
  const lines = csv.trim().split("\n");
  if (lines.length === 0) return [];

  const headers = lines[0].split(",").map((h) => h.trim());
  const data = [];

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(",");
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ? values[index].trim() : null;
    });
    data.push(row);
  }
  return data;
}

// Load network monitoring data
function loadNetworkData() {
  // Debounce: prevent duplicate requests
  if (fetchInProgress) return;
  fetchInProgress = true;

  // Update date range display
  updateNetworkDateRange();

  // Calculate time range based on offset (1-hour window)
  const now = new Date();
  const endTime = new Date(now.getTime() + networkHoursOffset * 60 * 60 * 1000);
  const startTime = new Date(endTime.getTime() - 1 * 60 * 60 * 1000); // 1 hour before end

  // Format timestamps for API (YYYY-MM-DD HH:MM:SS) in UTC
  const formatTimestamp = (date) => {
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    const hours = String(date.getUTCHours()).padStart(2, "0");
    const minutes = String(date.getUTCMinutes()).padStart(2, "0");
    const seconds = String(date.getUTCSeconds()).padStart(2, "0");
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  };

  const startTimeStr = formatTimestamp(startTime);
  const endTimeStr = formatTimestamp(endTime);

  // Update filename display
  const filenameEl = document.querySelector(".file-name");
  if (filenameEl) {
    const displayTime = formatTimestamp(endTime);
    filenameEl.textContent = `network_${displayTime.replace(
      /[-:\s]/g,
      "_"
    )}.csv`;
  }

  // Update live indicator
  const liveIndicator = document.querySelector(".live-indicator");
  if (liveIndicator) {
    liveIndicator.style.display = networkHoursOffset === 0 ? "flex" : "none";
  }

  // Load data with time range
  const url = `/csv/?start_time=${encodeURIComponent(
    startTimeStr
  )}&end_time=${encodeURIComponent(endTimeStr)}`;
  fetch(url)
    .then((response) => {
      if (!response.ok) {
        throw new Error("Failed to load data");
      }
      return response.text();
    })
    .then((csv) => {
      updateChartWithData(csv);
      updateNetworkNavButtons();
    })
    .catch((error) => {
      console.error("Error loading chart data:", error);
    })
    .finally(() => {
      fetchInProgress = false; // Release debounce lock
    });
}

// Update chart with CSV data
function updateChartWithData(csv) {
  const data = parseCSV(csv);

  if (data.length === 0) {
    console.warn("No data to display");
    return;
  }

  // Extract timestamps (HH:MM format)
  const timestamps = data.map((row) => {
    const ts = row.timestamp || "";
    const parts = ts.split(" ");
    if (parts.length > 1) {
      // Extract time portion (HH:MM:SS) and remove seconds
      const timeParts = parts[1].split(":");
      return `${timeParts[0]}:${timeParts[1]}`; // HH:MM only
    }
    return ts;
  });

  // Extract response times (handle nulls)
  const responseTimes = data.map((row) => {
    const rt = row.response_time;
    return rt === "null" || rt === null || rt === "" ? null : parseFloat(rt);
  });

  // Calculate success rates
  const successRates = data.map((row) => {
    const successCount = parseInt(row.success_count || 0);
    const totalCount = parseInt(row.total_count || 1);
    return (successCount / totalCount) * 100;
  });

  // Color-code success rate points
  const successColors = successRates.map((rate) =>
    rate === 100 ? "#98971a" : "#d65d0e"
  );

  // Update chart
  chart.data.labels = timestamps;
  chart.data.datasets[0].data = responseTimes;
  chart.data.datasets[1].data = successRates;
  chart.data.datasets[1].pointBackgroundColor = successColors;

  // Auto-scale Y-axis for response time
  const validTimes = responseTimes.filter((t) => t !== null);
  if (validTimes.length > 0) {
    const minTime = Math.min(...validTimes);
    const maxTime = Math.max(...validTimes);
    const padding = (maxTime - minTime) * 0.1 || 1;
    chart.options.scales.y.min = Math.max(0, minTime - padding);
    chart.options.scales.y.max = maxTime + padding;
  }

  chart.update("none"); // Use 'none' mode to skip animations for performance
}

// WebSocket connection
function connectWebSocket() {
  if (ws) return; // Already connected

  // Only connect if viewing live data
  if (networkHoursOffset !== 0) return;

  // Stop polling if it's running (we're switching to WebSocket)
  stopPolling();

  // Use /ws path through nginx proxy (location.host includes port)
  const wsUrl = `ws://${location.host}/ws`;
  updateWebSocketStatus("connecting");

  ws = new WebSocket(wsUrl);

  ws.onopen = function () {
    console.log("WebSocket connected");
    updateWebSocketStatus("connected");
    // Refresh chart on connection
    loadNetworkData();
  };

  ws.onmessage = function (event) {
    try {
      const message = JSON.parse(event.data);
      if (message.type === "update" && networkHoursOffset === 0) {
        // Reload chart data (only if still on live view)
        loadNetworkData();
      }
    } catch (e) {
      console.error("WebSocket message error:", e);
    }
  };

  ws.onerror = function (error) {
    console.error("WebSocket error:", error);
    updateWebSocketStatus("disconnected");
    startPolling();
  };

  ws.onclose = function () {
    console.log("WebSocket closed");
    updateWebSocketStatus("disconnected");
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
  updateWebSocketStatus("disconnected");
}

function updateWebSocketStatus(status) {
  const statusEl = document.querySelector(".websocket-status");
  if (!statusEl) return;

  statusEl.classList.remove("disconnected", "connecting");

  if (status === "connected") {
    statusEl.textContent = "WebSocket: Connected";
    statusEl.style.background = "#98971a"; // green
  } else if (status === "connecting") {
    statusEl.textContent = "WebSocket: Connecting...";
    statusEl.classList.add("connecting");
  } else {
    statusEl.textContent = "WebSocket: Disconnected (Polling)";
    statusEl.classList.add("disconnected");
  }
}

// HTTP polling fallback
function startPolling() {
  if (pollingInterval) return; // Already polling

  // Use requestIdleCallback for lower priority, better performance
  pollingInterval = setInterval(() => {
    if (document.visibilityState === "visible" && networkHoursOffset === 0) {
      if ("requestIdleCallback" in window) {
        requestIdleCallback(() => loadNetworkData(), { timeout: 2000 });
      } else {
        loadNetworkData();
      }
    }
  }, 60000); // Poll every 60 seconds
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
}

// Footer stats
let footerStatsInterval = null;
let startTime = Date.now();

function updateFooterStats() {
  // Update uptime
  const uptimeMs = Date.now() - startTime;
  const days = Math.floor(uptimeMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor(
    (uptimeMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)
  );
  const minutes = Math.floor((uptimeMs % (1000 * 60 * 60)) / (1000 * 60));

  let uptimeStr = "";
  if (days > 0) {
    uptimeStr = `${days}d ${hours}h`;
  } else if (hours > 0) {
    uptimeStr = `${hours}h ${minutes}m`;
  } else {
    uptimeStr = `${minutes}m`;
  }

  const uptimeEl = document.getElementById("footerUptime");
  if (uptimeEl) {
    uptimeEl.textContent = uptimeStr;
  }

  // Fetch DB size and stats from API
  fetch("/api/stats")
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (data) {
        const dbSizeEl = document.getElementById("footerDbSize");
        if (dbSizeEl) {
          dbSizeEl.textContent = data.db_size;
        }
      }
    })
    .catch((error) => {
      console.error("Error fetching footer stats:", error);
    });
}

// Initialize footer stats on load
document.addEventListener("DOMContentLoaded", function () {
  updateFooterStats();
  // Update footer stats every minute
  footerStatsInterval = setInterval(updateFooterStats, 60000);
});

// Docker Stats Management
let dockerStatsInterval = null;

function updateDockerStats() {
  fetch("/api/docker-stats")
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (data && data.available) {
        // Update CPU
        const cpuBar = document.getElementById("dockerCpuBar");
        const cpuValue = document.getElementById("dockerCpuValue");
        if (cpuBar && cpuValue) {
          const cpuPercent = data.cpu_percent || 0;
          cpuBar.style.width = `${cpuPercent}%`;
          cpuValue.textContent = `${cpuPercent.toFixed(1)}%`;

          // Apply color thresholds
          cpuBar.classList.remove("warning", "danger");
          if (cpuPercent >= 85) {
            cpuBar.classList.add("danger");
          } else if (cpuPercent >= 70) {
            cpuBar.classList.add("warning");
          }
        }

        // Update Memory
        const memBar = document.getElementById("dockerMemBar");
        const memValue = document.getElementById("dockerMemValue");
        if (memBar && memValue) {
          const memPercent = data.memory_percent || 0;
          memBar.style.width = `${memPercent}%`;
          memValue.textContent = `${data.memory_used} / ${data.memory_total}`;

          // Apply color thresholds
          memBar.classList.remove("warning", "danger");
          if (memPercent >= 85) {
            memBar.classList.add("danger");
          } else if (memPercent >= 70) {
            memBar.classList.add("warning");
          }
        }

        // Update Network I/O
        const netRx = document.getElementById("dockerNetRx");
        const netTx = document.getElementById("dockerNetTx");
        if (netRx && netTx) {
          netRx.textContent = data.network_rx || "--";
          netTx.textContent = data.network_tx || "--";
        }

        // Update Disk I/O
        const diskRead = document.getElementById("dockerDiskRead");
        const diskWrite = document.getElementById("dockerDiskWrite");
        if (diskRead && diskWrite) {
          diskRead.textContent = data.disk_read || "--";
          diskWrite.textContent = data.disk_write || "--";
        }
      } else {
        // Docker stats not available - show placeholder
        const cpuValue = document.getElementById("dockerCpuValue");
        const memValue = document.getElementById("dockerMemValue");
        const netRx = document.getElementById("dockerNetRx");
        const netTx = document.getElementById("dockerNetTx");
        const diskRead = document.getElementById("dockerDiskRead");
        const diskWrite = document.getElementById("dockerDiskWrite");

        if (cpuValue) cpuValue.textContent = "Unavailable";
        if (memValue) memValue.textContent = "Unavailable";
        if (netRx) netRx.textContent = "--";
        if (netTx) netTx.textContent = "--";
        if (diskRead) diskRead.textContent = "--";
        if (diskWrite) diskWrite.textContent = "--";
      }
    })
    .catch((error) => {
      console.error("Error fetching Docker stats:", error);
    });
}

// Initialize Docker stats on load
document.addEventListener("DOMContentLoaded", function () {
  updateDockerStats();
  // Update Docker stats every 30 seconds
  dockerStatsInterval = setInterval(updateDockerStats, 30000);
});

// Old navigation functions removed - now using time-based navigation
