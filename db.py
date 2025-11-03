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

        self.conn.commit()

    def insert_log(self, timestamp, status, response_time, success_count, total_count, failed_count):
        """Insert a single log entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO network_logs
            (timestamp, status, response_time, success_count, total_count, failed_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, status, response_time, success_count, total_count, failed_count))
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

    def cleanup_old_logs(self, days=10):
        """Delete logs older than specified days."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM network_logs
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))

        deleted = cursor.rowcount
        self.conn.commit()

        # Vacuum to reclaim space
        self.conn.execute("VACUUM")

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
