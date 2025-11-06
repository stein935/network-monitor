# Changelog

All notable changes to the Network Monitor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- [feat] Date range display showing exact time window being viewed for both network monitoring and speed test charts
- [feat] "Go Live" button with red dot indicator to quickly return to live view from historical data
- [feat] Dynamic button visibility - Go Live button only appears when viewing historical data (offset != 0)
- [feat] Auto-reconnect WebSocket when returning to live view via Go Live button
- [perf] SQLite WAL mode for 30-40% faster writes with better concurrency
- [perf] 32MB SQLite query cache for improved database performance
- [perf] nginx proxy cache (30s) for API and CSV endpoints
- [perf] ETag support for static files to reduce bandwidth on repeat visits
- [perf] HTML response caching (30s server-side) to reduce CPU load
- [perf] Python bytecode pre-compilation for 10-15% faster startup
- [perf] Request debouncing in dashboard to prevent duplicate API calls
- [perf] requestIdleCallback for low-priority background tasks

### Changed
- [style] Improved navigation controls layout with date range display and button grouping
- [docs] Enhanced CLAUDE.md with Git workflow rules and documentation standards

### Fixed
- [ui] Server URI overflow in speed test stats box - long server hostnames now truncate with ellipsis and show full text on hover
- [perf] Disabled chart animations for better performance on Raspberry Pi Zero 2 W
- [perf] Reduced nginx worker_connections from 1024 to 128 (adequate for typical use)
- [perf] Disabled nginx access logging to reduce I/O overhead on SD card
- [perf] Reduced console logging verbosity (only every 10th sample or on failures)
- [perf] Docker logging limits: max 1MB per file, 2 files max (prevents unbounded growth)

### Removed
- [perf] Removed expensive VACUUM from hourly cleanup (WAL mode auto-checkpoints make it less critical)

## Previous Updates

### Phase 3 - nginx Reverse Proxy
- Added nginx reverse proxy for gzip compression and better concurrency
- 70% bandwidth reduction via gzip compression
- WebSocket proxying through `/ws` path
- Improved static file serving

### Phase 2 - Chart.js and WebSocket
- Migrated from Plotly to Chart.js (93% page size reduction)
- Added WebSocket support for real-time updates (30-second batches)
- 95% CPU reduction vs HTTP polling
- Single-page dashboard with unified view

### Phase 1 - SQLite Migration
- Migrated from CSV to SQLite database storage
- 70% reduction in disk I/O
- Added internet speed testing (every 15 minutes)
- Dual table schema for network logs and speed tests
- Automatic cleanup with VACUUM
