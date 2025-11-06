#!/usr/bin/env python3

"""
SQLite database handler for network monitoring data.
Replaces CSV files with more efficient SQLite storage.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import sys


class NetworkMonitorDB:
    def __init__(self, db_path="logs/network_monitor.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.init_db()

    def init_db(self):
        """Initialize database with schema."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)

        # Performance optimizations for Pi Zero 2 W
        self.conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
        self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
        self.conn.execute("PRAGMA cache_size=-32000")  # Use 32MB cache for queries

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS network_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                response_time REAL,
                success_count INTEGER NOT NULL,
                total_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for faster queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON network_logs(timestamp)
        """)

        # Speed test table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS speed_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                download_mbps REAL NOT NULL,
                upload_mbps REAL NOT NULL,
                ping_ms REAL,
                server_host TEXT,
                server_name TEXT,
                server_country TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for faster speed test queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_speed_timestamp
            ON speed_tests(timestamp)
        """)

        self.conn.commit()

    def insert_log(self, timestamp, status, response_time, success_count, total_count, failed_count):
        """Insert a single log entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO network_logs
            (timestamp, status, response_time, success_count, total_count, failed_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, status, response_time, success_count, total_count, failed_count))

        # Commit immediately - WAL mode makes this efficient
        self.conn.commit()

        return cursor.lastrowid

    def get_logs_by_hour(self, date_str, hour):
        """Get all logs for a specific hour."""
        # Format: YYYY-MM-DD HH:
        start_time = f"{date_str} {hour:02d}:"
        end_time = f"{date_str} {hour:02d}:59:59"

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, status, response_time, success_count, total_count, failed_count
            FROM network_logs
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start_time, end_time))

        return cursor.fetchall()

    def get_logs_by_date_range(self, start_date, end_date):
        """Get all logs within a date range."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, status, response_time, success_count, total_count, failed_count
            FROM network_logs
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start_date, end_date))

        return cursor.fetchall()

    def get_available_hours(self):
        """Get list of all available hours with data."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT
                date(timestamp) as date,
                strftime('%H', timestamp) as hour,
                COUNT(*) as count
            FROM network_logs
            GROUP BY date, hour
            ORDER BY date DESC, hour DESC
        """)

        return cursor.fetchall()

    def export_to_csv(self, date_str, hour):
        """Export a specific hour to CSV format."""
        # Ensure hour is an integer
        if isinstance(hour, str):
            hour = int(hour)

        logs = self.get_logs_by_hour(date_str, hour)

        csv_lines = ["timestamp, status, response_time, success_count, total_count, failed_count"]
        for log in logs:
            timestamp, status, response_time, success_count, total_count, failed_count = log
            # Format response_time as null if None
            rt_str = "null" if response_time is None else f"{response_time:.3f}"
            csv_lines.append(f"{timestamp}, {status}, {rt_str}, {success_count}, {total_count}, {failed_count}")

        return "\n".join(csv_lines)

    def export_to_csv_range(self, start_time, end_time):
        """Export logs within a time range to CSV format.

        Args:
            start_time: ISO format timestamp (YYYY-MM-DD HH:MM:SS)
            end_time: ISO format timestamp (YYYY-MM-DD HH:MM:SS)
        """
        logs = self.get_logs_by_date_range(start_time, end_time)

        csv_lines = ["timestamp, status, response_time, success_count, total_count, failed_count"]
        for log in logs:
            timestamp, status, response_time, success_count, total_count, failed_count = log
            # Format response_time as null if None
            rt_str = "null" if response_time is None else f"{response_time:.3f}"
            csv_lines.append(f"{timestamp}, {status}, {rt_str}, {success_count}, {total_count}, {failed_count}")

        return "\n".join(csv_lines)

    def cleanup_old_logs(self, days=10):
        """Delete logs older than specified days."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM network_logs
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))

        deleted = cursor.rowcount

        # Also cleanup old speed tests
        cursor.execute("""
            DELETE FROM speed_tests
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))

        deleted += cursor.rowcount
        self.conn.commit()

        # VACUUM is expensive on Pi - only run if significant deletions (>10% of DB)
        # WAL mode auto-checkpoints, so VACUUM is less critical
        # Consider running VACUUM manually during maintenance windows instead

        return deleted

    def get_latest_log(self):
        """Get the most recent log entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, status, response_time, success_count, total_count, failed_count
            FROM network_logs
            ORDER BY id DESC
            LIMIT 1
        """)

        return cursor.fetchone()

    def get_earliest_log(self):
        """Get the earliest log entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, status, response_time, success_count, total_count, failed_count
            FROM network_logs
            ORDER BY id ASC
            LIMIT 1
        """)

        return cursor.fetchone()

    def insert_speed_test(self, timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country):
        """Insert a speed test result."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO speed_tests
            (timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country))
        self.conn.commit()
        return cursor.lastrowid

    def get_latest_speed_test(self):
        """Get the most recent speed test result."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country
            FROM speed_tests
            ORDER BY id DESC
            LIMIT 1
        """)
        return cursor.fetchone()

    def get_speed_tests_by_date(self, date_str):
        """Get all speed tests for a specific date."""
        start_time = f"{date_str} 00:00:00"
        end_time = f"{date_str} 23:59:59"

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country
            FROM speed_tests
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start_time, end_time))

        return cursor.fetchall()

    def get_recent_speed_tests(self, hours=24):
        """Get speed tests from the last N hours."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country
            FROM speed_tests
            WHERE timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        """, (hours,))

        return cursor.fetchall()

    def get_speed_tests_range(self, start_time=None, end_time=None):
        """Get speed tests within a specific time range.

        Args:
            start_time: ISO format timestamp (YYYY-MM-DD HH:MM:SS) or None for no start limit
            end_time: ISO format timestamp (YYYY-MM-DD HH:MM:SS) or None for no end limit
        """
        cursor = self.conn.cursor()

        if start_time and end_time:
            cursor.execute("""
                SELECT timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country
                FROM speed_tests
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            """, (start_time, end_time))
        elif start_time:
            cursor.execute("""
                SELECT timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country
                FROM speed_tests
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (start_time,))
        elif end_time:
            cursor.execute("""
                SELECT timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country
                FROM speed_tests
                WHERE timestamp <= ?
                ORDER BY timestamp ASC
            """, (end_time,))
        else:
            cursor.execute("""
                SELECT timestamp, download_mbps, upload_mbps, ping_ms, server_host, server_name, server_country
                FROM speed_tests
                ORDER BY timestamp ASC
            """)

        return cursor.fetchall()

    def cleanup_old_speed_tests(self, days=30):
        """Delete speed tests older than specified days."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM speed_tests
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))

        deleted = cursor.rowcount
        self.conn.commit()
        return deleted

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    # Test the database
    db = NetworkMonitorDB("logs/network_monitor.db")

    # Insert a test log
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_id = db.insert_log(now, "CONNECTED", 15.234, 5, 5, 0)
    print(f"Inserted log with ID: {log_id}")

    # Get available hours
    hours = db.get_available_hours()
    print(f"\nAvailable hours: {len(hours)}")
    for date, hour, count in hours[:5]:
        print(f"  {date} {hour}:00 - {count} entries")

    # Export to CSV
    if hours:
        date, hour, _ = hours[0]
        csv = db.export_to_csv(date, hour)
        print(f"\nCSV export preview:")
        print("\n".join(csv.split("\n")[:5]))

    db.close()
