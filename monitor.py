#!/usr/bin/env python3

"""
Network monitor daemon that writes to SQLite database.
Replaces monitor.sh for better performance and SQLite integration.
"""

import subprocess
import time
import sys
from datetime import datetime
from pathlib import Path
import re
import threading
import json

# Add parent directory to path to import db module
sys.path.insert(0, str(Path(__file__).parent))
from db import NetworkMonitorDB


class NetworkMonitor:
    def __init__(self, frequency=1, sample_size=5, log_retention_days=30):
        self.frequency = frequency
        self.sample_size = sample_size
        self.log_retention_days = log_retention_days
        self.db = NetworkMonitorDB()
        self.last_cleanup = time.time()
        self.cleanup_interval = 3600  # Clean up once per hour
        self.print_count = 0  # Track prints for reduced verbosity

    def ping_host(self, host="8.8.8.8"):
        """Ping a host and return response time in ms, or None if failed."""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", host],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                # Extract avg response time (works on both macOS and Linux)
                # macOS format: round-trip min/avg/max/stddev = 14.123/15.456/16.789/1.234 ms
                # Linux format: rtt min/avg/max/mdev = 14.123/15.456/16.789/1.234 ms
                match = re.search(r'(round-trip|rtt)[^=]*=\s*[\d.]+/([\d.]+)', result.stdout)
                if match:
                    return float(match.group(2))

            return None
        except Exception as e:
            print(f"[!] Ping error: {e}", file=sys.stderr)
            return None

    def collect_sample(self):
        """Collect a sample of pings and return statistics."""
        response_times = []

        for i in range(self.sample_size):
            response_time = self.ping_host()
            response_times.append(response_time)

            # Wait between samples (except on last one)
            if i < self.sample_size - 1:
                time.sleep(self.frequency)

        # Calculate statistics
        success_count = sum(1 for rt in response_times if rt is not None)
        failed_count = self.sample_size - success_count
        total_count = self.sample_size

        # Calculate average response time (excluding failures)
        if success_count > 0:
            avg_response_time = sum(rt for rt in response_times if rt is not None) / success_count
            status = "CONNECTED"
        else:
            avg_response_time = None
            status = "DISCONNECTED"

        return status, avg_response_time, success_count, total_count, failed_count

    def cleanup_old_logs(self):
        """Clean up logs older than retention period."""
        deleted = self.db.cleanup_old_logs(self.log_retention_days)
        if deleted > 0:
            print(f"[*] Cleaned up {deleted} old log/speed test entries")

    def run_speed_test(self):
        """Run internet speed test using speedtest-cli."""
        try:
            print("[*] Running speed test...")
            result = subprocess.run(
                ["speedtest-cli", "--json"],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)

                # Extract relevant data
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                download_mbps = data.get("download", 0) / 1_000_000  # Convert to Mbps
                upload_mbps = data.get("upload", 0) / 1_000_000  # Convert to Mbps
                ping_ms = data.get("ping", None)

                # Server info
                server = data.get("server", {})
                server_host = server.get("host", "")
                server_name = server.get("name", "")
                server_country = server.get("country", "")

                # Insert into database
                test_id = self.db.insert_speed_test(
                    timestamp, download_mbps, upload_mbps, ping_ms,
                    server_host, server_name, server_country
                )

                print(f"[{timestamp}] Speed Test - Download: {download_mbps:.2f} Mbps, "
                      f"Upload: {upload_mbps:.2f} Mbps, Ping: {ping_ms:.2f} ms "
                      f"[Server: {server_name}, {server_country}] [ID: {test_id}]")
            else:
                print(f"[!] Speed test failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            print("[!] Speed test timed out")
        except json.JSONDecodeError as e:
            print(f"[!] Speed test JSON parse error: {e}")
        except Exception as e:
            print(f"[!] Speed test error: {e}", file=sys.stderr)

    def speed_test_loop(self):
        """Separate thread for running speed tests every 15 minutes."""
        print("[*] Starting speed test loop (every 15 minutes)...")

        # Initial delay of 30 seconds to let the monitor start up
        time.sleep(30)

        while True:
            try:
                self.run_speed_test()
            except Exception as e:
                print(f"[!] Speed test loop error: {e}", file=sys.stderr)

            # Wait 15 minutes before next test
            time.sleep(900)  # 900 seconds = 15 minutes

    def run(self):
        """Main monitoring loop."""
        print("[*] Starting network monitor daemon (Python/SQLite version)...")
        print(f"[*] Frequency: {self.frequency}s, Sample size: {self.sample_size}")
        print(f"[*] Log retention: {self.log_retention_days} days")
        print(f"[*] Database: {self.db.db_path}")
        print("[*] Press Ctrl+C to stop")
        print()

        # Initial cleanup
        self.cleanup_old_logs()

        # Start speed test thread
        speed_test_thread = threading.Thread(target=self.speed_test_loop, daemon=True)
        speed_test_thread.start()

        try:
            while True:
                iteration_start = time.time()

                # Check if it's time to cleanup
                if (iteration_start - self.last_cleanup) >= self.cleanup_interval:
                    self.cleanup_old_logs()
                    self.last_cleanup = iteration_start

                # Collect sample
                status, avg_response_time, success_count, total_count, failed_count = self.collect_sample()

                # Get current timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Insert into database (WAL mode makes individual commits efficient)
                log_id = self.db.insert_log(
                    timestamp, status, avg_response_time,
                    success_count, total_count, failed_count
                )

                # Increment print counter
                self.print_count += 1

                # Print status (reduce verbosity - only every 10th iteration or on failures)
                should_print = (self.print_count % 10 == 0) or (status == "DISCONNECTED")
                if should_print:
                    if avg_response_time is not None:
                        print(f"[{timestamp}] {status} - {avg_response_time:.2f}ms ({success_count}/{total_count}) [ID: {log_id}]")
                    else:
                        print(f"[{timestamp}] {status} - null ({success_count}/{total_count}) [ID: {log_id}]")

                # Sleep before next sample (account for time taken)
                elapsed = time.time() - iteration_start
                sleep_time = max(0, self.frequency - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n[*] Stopping monitor...")
            self.db.close()
            sys.exit(0)


if __name__ == "__main__":
    # Parse command line arguments
    frequency = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    monitor = NetworkMonitor(frequency=frequency, sample_size=sample_size)
    monitor.run()
