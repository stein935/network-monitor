#!/usr/bin/env python3

"""
API request handlers for network monitor server.
"""

import json
import subprocess
import urllib.parse
from urllib.parse import urlparse, parse_qs
from utils import format_bytes


def handle_network_logs_earliest(handler):
    """Handle /api/network-logs/earliest endpoint."""
    try:
        earliest = handler.db.get_earliest_log()

        if earliest:
            (
                timestamp,
                status,
                response_time,
                success_count,
                total_count,
                failed_count,
            ) = earliest
            data = {
                "timestamp": timestamp,
                "status": status,
                "response_time": response_time,
                "success_count": success_count,
                "total_count": total_count,
                "failed_count": failed_count,
            }
            _send_json_response(handler, data)
        else:
            handler.send_error(404, "No network log data available")
    except Exception as e:
        handler.send_error(500, f"Error fetching network log data: {str(e)}")


def handle_speed_tests_latest(handler):
    """Handle /api/speed-tests/latest endpoint."""
    try:
        latest = handler.db.get_latest_speed_test()

        if latest:
            (
                timestamp,
                download_mbps,
                upload_mbps,
                ping_ms,
                server_host,
                server_name,
                server_country,
            ) = latest
            data = {
                "timestamp": timestamp,
                "download_mbps": round(download_mbps, 2),
                "upload_mbps": round(upload_mbps, 2),
                "ping_ms": round(ping_ms, 2) if ping_ms else None,
                "server_host": server_host,
                "server_name": server_name,
                "server_country": server_country,
            }
            _send_json_response(handler, data)
        else:
            handler.send_error(404, "No speed test data available")
    except Exception as e:
        handler.send_error(500, f"Error fetching speed test data: {str(e)}")


def handle_speed_tests_earliest(handler):
    """Handle /api/speed-tests/earliest endpoint."""
    try:
        earliest = handler.db.get_earliest_speed_test()

        if earliest:
            (
                timestamp,
                download_mbps,
                upload_mbps,
                ping_ms,
                server_host,
                server_name,
                server_country,
            ) = earliest
            data = {
                "timestamp": timestamp,
                "download_mbps": round(download_mbps, 2),
                "upload_mbps": round(upload_mbps, 2),
                "ping_ms": round(ping_ms, 2) if ping_ms else None,
                "server_host": server_host,
                "server_name": server_name,
                "server_country": server_country,
            }
            _send_json_response(handler, data)
        else:
            handler.send_error(404, "No speed test data available")
    except Exception as e:
        handler.send_error(500, f"Error fetching earliest speed test data: {str(e)}")


def handle_speed_tests_recent(handler):
    """Handle /api/speed-tests/recent endpoint."""
    try:
        parsed = urlparse(handler.path)
        params = parse_qs(parsed.query)

        # Get start_time and end_time from query params
        start_time = params.get("start_time", [None])[0]
        end_time = params.get("end_time", [None])[0]

        # Use time range if provided, otherwise default to last 24 hours
        if start_time or end_time:
            tests = handler.db.get_speed_tests_range(start_time, end_time)
        else:
            tests = handler.db.get_recent_speed_tests(hours=24)

        results = []
        for test in tests:
            (
                timestamp,
                download_mbps,
                upload_mbps,
                ping_ms,
                server_host,
                server_name,
                server_country,
            ) = test
            results.append(
                {
                    "timestamp": timestamp,
                    "download_mbps": round(download_mbps, 2),
                    "upload_mbps": round(upload_mbps, 2),
                    "ping_ms": round(ping_ms, 2) if ping_ms else None,
                    "server_host": server_host,
                    "server_name": server_name,
                    "server_country": server_country,
                }
            )

        _send_json_response(handler, results)
    except Exception as e:
        handler.send_error(500, f"Error fetching speed test data: {str(e)}")


def handle_stats(handler):
    """Handle /api/stats endpoint."""
    try:
        # Get database file size
        db_path = handler.logs_dir / "network_monitor.db"
        db_size_bytes = db_path.stat().st_size if db_path.exists() else 0

        # Convert to human-readable format
        if db_size_bytes < 1024:
            db_size_str = f"{db_size_bytes}B"
        elif db_size_bytes < 1024 * 1024:
            db_size_str = f"{db_size_bytes / 1024:.1f}KB"
        elif db_size_bytes < 1024 * 1024 * 1024:
            db_size_str = f"{db_size_bytes / (1024 * 1024):.1f}MB"
        else:
            db_size_str = f"{db_size_bytes / (1024 * 1024 * 1024):.2f}GB"

        # Get log counts
        network_count = handler.db.get_log_count()
        speed_count = handler.db.get_speed_test_count()

        data = {
            "db_size": db_size_str,
            "db_size_bytes": db_size_bytes,
            "network_log_count": network_count,
            "speed_test_count": speed_count,
        }
        _send_json_response(handler, data)
    except Exception as e:
        handler.send_error(500, f"Error fetching stats: {str(e)}")


def handle_docker_stats(handler):
    """Handle /api/docker-stats endpoint."""
    try:
        # Run docker stats command for network-monitor container
        result = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                "network-monitor",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Parse JSON output from docker stats
            try:
                stats = json.loads(result.stdout.strip())
            except json.JSONDecodeError as e:
                # JSON parse error - return debug info
                data = {
                    "available": False,
                    "error": f"JSON parse error: {str(e)}",
                    "stdout": result.stdout[:200],
                    "stderr": result.stderr[:200] if result.stderr else "",
                }
                _send_json_response(handler, data)
                return

            # Extract and format the data
            cpu_percent = stats.get("CPUPerc", "0%").rstrip("%")

            # Memory usage (e.g., "125MB / 250MB")
            mem_usage = stats.get("MemUsage", "0B / 0B")
            mem_parts = mem_usage.split(" / ")
            mem_used = mem_parts[0] if len(mem_parts) > 0 else "0B"
            mem_total = mem_parts[1] if len(mem_parts) > 1 else "0B"
            mem_percent_str = stats.get("MemPerc", "0%").rstrip("%")

            # Fallback for ARM platforms (Raspberry Pi) where docker stats shows 0B / 0B
            # This happens because Docker resource limits may not be visible on ARM
            # Read actual memory usage from /proc/meminfo instead
            if mem_used == "0B" or mem_total == "0B":
                try:
                    # Read memory from /proc/meminfo (container's view)
                    with open("/proc/meminfo", "r") as f:
                        meminfo = f.read()

                    # Parse MemTotal and MemAvailable
                    mem_total_kb = 0
                    mem_available_kb = 0
                    for line in meminfo.split("\n"):
                        if line.startswith("MemTotal:"):
                            mem_total_kb = int(line.split()[1])
                        elif line.startswith("MemAvailable:"):
                            mem_available_kb = int(line.split()[1])

                    # Calculate used memory
                    mem_used_kb = mem_total_kb - mem_available_kb

                    mem_used = format_bytes(mem_used_kb)
                    mem_total = format_bytes(mem_total_kb)
                    mem_percent_str = (
                        str(round((mem_used_kb / mem_total_kb * 100), 2))
                        if mem_total_kb > 0
                        else "0"
                    )
                except Exception:
                    # If /proc read fails, keep docker stats values
                    pass

            mem_percent = float(mem_percent_str)

            # Network I/O (e.g., "12.5MB / 3.2MB")
            net_io = stats.get("NetIO", "0B / 0B")
            net_parts = net_io.split(" / ")
            net_rx = net_parts[0] if len(net_parts) > 0 else "0B"
            net_tx = net_parts[1] if len(net_parts) > 1 else "0B"

            # Block I/O (e.g., "45.2MB / 12.8MB")
            block_io = stats.get("BlockIO", "0B / 0B")
            block_parts = block_io.split(" / ")
            block_read = block_parts[0] if len(block_parts) > 0 else "0B"
            block_write = block_parts[1] if len(block_parts) > 1 else "0B"

            data = {
                "cpu_percent": float(cpu_percent),
                "memory_used": mem_used,
                "memory_total": mem_total,
                "memory_percent": mem_percent,
                "network_rx": net_rx,
                "network_tx": net_tx,
                "disk_read": block_read,
                "disk_write": block_write,
                "available": True,
            }
        else:
            # Docker not available or container not running
            data = {
                "available": False,
                "error": "Container not running or stats unavailable",
                "returncode": result.returncode,
                "stdout": result.stdout[:200] if result.stdout else "",
                "stderr": result.stderr[:200] if result.stderr else "",
            }

        _send_json_response(handler, data)
    except subprocess.TimeoutExpired:
        data = {"available": False, "error": "Docker stats timeout"}
        _send_json_response(handler, data)
    except Exception as e:
        data = {"available": False, "error": str(e)}
        _send_json_response(handler, data)


def handle_csv_export(handler):
    """Handle /csv/ endpoint."""
    try:
        parsed = urlparse(handler.path)
        params = parse_qs(parsed.query)

        # Get start_time and end_time from query params
        start_time = params.get("start_time", [None])[0]
        end_time = params.get("end_time", [None])[0]

        # Use time range if provided, otherwise use legacy date/hour format
        if start_time and end_time:
            csv_content = handler.db.export_to_csv_range(start_time, end_time)
        else:
            # Legacy path format: /csv/YYYY-MM-DD/HH
            csv_path = urllib.parse.unquote(parsed.path[5:])  # Remove /csv/ prefix

            # Parse date and hour from path
            if "/" not in csv_path:
                handler.send_error(
                    400,
                    "Invalid path format. Expected: /csv/YYYY-MM-DD/HH or /csv?start_time=...&end_time=...",
                )
                return

            parts = csv_path.split("/")
            if len(parts) < 2:
                handler.send_error(
                    400,
                    "Invalid path format. Expected: /csv/YYYY-MM-DD/HH or /csv?start_time=...&end_time=...",
                )
                return

            date_str = parts[0]  # YYYY-MM-DD
            hour = int(parts[1])  # HH (0-23)

            # Export from database
            csv_content = handler.db.export_to_csv(date_str, hour)

        if (
            not csv_content
            or csv_content
            == "timestamp, status, response_time, success_count, total_count, failed_count"
        ):
            handler.send_error(404, "No data found")
            return

        content = csv_content.encode("utf-8")

        handler.send_response(200)
        handler.send_header("Content-type", "text/csv")
        handler.send_header("Content-Length", len(content))
        handler.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(content)
    except Exception as e:
        import traceback

        traceback.print_exc()
        handler.send_error(500, f"Error exporting CSV: {str(e)}")


def _send_json_response(handler, data):
    """
    Helper to send JSON response with standard headers.

    Args:
        handler: Request handler instance
        data: Data to serialize as JSON
    """
    content = json.dumps(data).encode("utf-8")

    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Content-Length", len(content))
    handler.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(content)
