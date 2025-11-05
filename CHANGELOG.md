# Changelog

All notable changes to the Network Monitor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- [feat] Date range display showing exact time window being viewed for both network monitoring and speed test charts
- [feat] "Go Live" button with red dot indicator to quickly return to live view from historical data
- [feat] Dynamic button visibility - Go Live button only appears when viewing historical data (offset != 0)
- [feat] Auto-reconnect WebSocket when returning to live view via Go Live button

### Changed
- [style] Improved navigation controls layout with date range display and button grouping
- [docs] Enhanced CLAUDE.md with Git workflow rules and documentation standards

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
