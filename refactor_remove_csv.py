#!/usr/bin/env python3
"""
Script to refactor serve.py to remove CSV filename concept.
Changes URLs from /view/YYYY-MM-DD/monitor_YYYYMMDD_HH.csv to /view/YYYY-MM-DD/HH
"""

import re

def refactor_serve_py():
    with open('serve.py', 'r') as f:
        content = f.read()

    original_content = content

    # 1. Fix /csv/ endpoint path handling
    print("[1/10] Fixing /csv/ endpoint...")
    content = re.sub(
        r'# Path format: /csv/YYYY-MM-DD/HH or /csv/YYYY-MM-DD/monitor_YYYYMMDD_HH\.csv\n\s+csv_path = urllib\.parse\.unquote\(self\.path\[5:\]\).*?\n.*?\n.*?# Parse date and hour from path.*?\n.*?if "/" in csv_path:.*?\n.*?parts = csv_path\.split\("/"\).*?\n.*?date_str = parts\[0\].*?\n.*?\n.*?# Extract hour from filename or second part.*?\n.*?if len\(parts\) > 1:.*?\n.*?if parts\[1\]\.endswith\("\.csv"\):.*?\n.*?# Format: monitor_YYYYMMDD_HH\.csv.*?\n.*?hour_str = parts\[1\]\.split\("_"\)\[-1\]\.replace\("\.csv", ""\).*?\n.*?hour = int\(hour_str\).*?\n.*?else:.*?\n.*?# Format: HH.*?\n.*?hour = int\(parts\[1\]\).*?\n.*?else:.*?\n.*?self\.send_error\(400, "Invalid CSV path format"\).*?\n.*?return.*?\n.*?else:.*?\n.*?self\.send_error\(400, "Invalid CSV path format"\).*?\n.*?return',
        '''# Path format: /csv/YYYY-MM-DD/HH
                csv_path = urllib.parse.unquote(self.path[5:])  # Remove /csv/ prefix

                # Parse date and hour from path
                if "/" not in csv_path:
                    self.send_error(400, "Invalid path format. Expected: /csv/YYYY-MM-DD/HH")
                    return

                parts = csv_path.split("/")
                if len(parts) < 2:
                    self.send_error(400, "Invalid path format. Expected: /csv/YYYY-MM-DD/HH")
                    return

                date_str = parts[0]  # YYYY-MM-DD
                hour = int(parts[1])  # HH (0-23)''',
        content,
        flags=re.DOTALL
    )

    # 2. Fix /view/ endpoint path handling
    print("[2/10] Fixing /view/ endpoint...")
    content = re.sub(
        r'# Serve specific visualization\n\s+# Path format: /view/YYYY-MM-DD/monitor_YYYYMMDD_HHMMSS\.csv\n\s+try:.*?\n.*?# Extract the path components.*?\n.*?parts = self\.path\[6:\]\.split\("/"\).*?\n.*?if len\(parts\) < 2:.*?\n.*?self\.send_error\(400, "Invalid path format"\).*?\n.*?return.*?\n.*?\n.*?date_str = parts\[0\].*?\n.*?csv_filename = "/".join\(parts\[1:\]\).*?\n.*?\n.*?# Extract hour from filename \(format: monitor_YYYYMMDD_HH\.csv\).*?\n.*?hour_str = csv_filename\.split\("_"\)\[-1\]\.replace\("\.csv", ""\).*?\n.*?hour = int\(hour_str\)',
        '''# Serve specific visualization
            # Path format: /view/YYYY-MM-DD/HH
            try:
                # Extract the path components
                parts = self.path[6:].split("/")  # Remove /view/ prefix
                if len(parts) < 2:
                    self.send_error(400, "Invalid path format. Expected: /view/YYYY-MM-DD/HH")
                    return

                date_str = parts[0]  # YYYY-MM-DD
                hour = int(parts[1])  # HH (0-23)''',
        content,
        flags=re.DOTALL
    )

    # 3. Remove csv_file creation and update is_current_hour logic
    print("[3/10] Updating current hour detection...")
    content = re.sub(
        r'# For compatibility, create a pseudo csv_file path.*?\n.*?csv_file = self\.logs_dir / date_str / "csv" / csv_filename.*?\n.*?\n.*?# Check if this is the current hour\'s file.*?\n.*?now = datetime\.now\(\).*?\n.*?current_date_str = now\.strftime\("%Y-%m-%d"\).*?\n.*?current_hour_str = now\.strftime\("%Y%m%d_%H"\).*?\n.*?is_current_hour = \(.*?\n.*?date_str == current_date_str and current_hour_str in csv_filename.*?\n.*?\).*?\n.*?\n.*?print\(.*?\n.*?f"\\n\[\*\] Serving visualization for: \{csv_file\.name\}.*?\n.*?\)',
        '''# Check if this is the current hour
                now = datetime.now()
                current_date_str = now.strftime("%Y-%m-%d")
                current_hour = now.hour
                is_current_hour = (date_str == current_date_str and hour == current_hour)

                print(
                    f"\\n[*] Serving visualization for: {date_str} hour {hour} (current_hour={is_current_hour})"
                )''',
        content,
        flags=re.DOTALL
    )

    # 4. Remove html_file creation
    print("[4/10] Removing unused html_file...")
    content = re.sub(
        r'html_dir = self\.logs_dir / date_str / "html".*?\n.*?html_file = html_dir / f"\{csv_file\.stem\}_visualization\.html".*?\n.*?\n',
        '',
        content,
        flags=re.DOTALL
    )

    # 5. Update method calls to remove csv_file and csv_filename parameters
    print("[5/10] Updating Chart.js method calls...")
    content = re.sub(
        r'html_content = self\._generate_chartjs_with_websocket\(.*?csv_file, date_str, csv_filename.*?\)',
        'html_content = self._generate_chartjs_with_websocket(date_str, hour)',
        content
    )
    content = re.sub(
        r'html_content = self\._generate_chartjs_static\(.*?csv_file, date_str, csv_filename.*?\)',
        'html_content = self._generate_chartjs_static(date_str, hour)',
        content
    )

    # 6. Update navigation call
    print("[6/10] Updating navigation call...")
    content = re.sub(
        r'prev_url, next_url = self\._get_navigation_urls\(date_str, csv_filename\)',
        'prev_url, next_url = self._get_navigation_urls(date_str, hour)',
        content
    )

    # 7. Update view_url in index generation
    print("[7/10] Updating index view URLs...")
    content = re.sub(
        r'view_url = f"/view/\{date_str\}/\{filename\}"',
        'view_url = f"/view/{date_str}/{hour}"',
        content
    )

    # 8. Update formatted_time to use hour variable
    print("[8/10] Updating formatted time...")
    content = re.sub(
        r'formatted_time = f"\{hour\}:00 - \{hour\}:59"',
        'formatted_time = f"{hour:02d}:00 - {hour:02d}:59"',
        content
    )

    # 9. Update _get_navigation_urls signature and implementation
    print("[9/10] Updating _get_navigation_urls...")
    content = re.sub(
        r'def _get_navigation_urls\(self, date_str, csv_filename\):.*?\n.*?"""Get previous and next URLs from database available hours\.""".*?\n.*?# Extract hour from filename \(monitor_20251103_23\.csv -> 23\).*?\n.*?hour_str = csv_filename\.split\("_"\)\[-1\]\.replace\("\.csv", ""\).*?\n.*?hour = int\(hour_str\)',
        'def _get_navigation_urls(self, date_str, hour):\n        """Get previous and next URLs from database available hours."""',
        content
    )

    # Update navigation URL generation
    content = re.sub(
        r'prev_filename = \(.*?\n.*?f"monitor_\{prev_date\.replace\(\'-\', \'\'\)\}_\{prev_hour:02d\}\.csv".*?\n.*?\).*?\n.*?prev_url = f"/view/\{prev_date\}/\{prev_filename\}"',
        'prev_url = f"/view/{prev_date}/{prev_hour}"',
        content
    )
    content = re.sub(
        r'next_filename = \(.*?\n.*?f"monitor_\{next_date\.replace\(\'-\', \'\'\)\}_\{next_hour:02d\}\.csv".*?\n.*?\).*?\n.*?next_url = f"/view/\{next_date\}/\{next_filename\}"',
        'next_url = f"/view/{next_date}/{next_hour}"',
        content
    )

    # 10. Update method signatures
    print("[10/10] Updating method signatures...")
    content = re.sub(
        r'def _generate_chartjs_with_websocket\(self, csv_file, date_str, csv_filename\):',
        'def _generate_chartjs_with_websocket(self, date_str, hour):',
        content
    )
    content = re.sub(
        r'def _generate_chartjs_static\(self, csv_file, date_str, csv_filename\):',
        'def _generate_chartjs_static(self, date_str, hour):',
        content
    )

    # Update csv_url generation
    content = re.sub(
        r'csv_url = f"/csv/\{date_str\}/\{csv_filename\}"',
        'csv_url = f"/csv/{date_str}/{hour}"',
        content
    )

    # Update page titles
    content = re.sub(
        r'<title>Network Monitor - \{csv_filename\} \(Live\)</title>',
        '<title>Network Monitor - {date_str} {hour:02d}:00 (Live)</title>',
        content
    )
    content = re.sub(
        r'<title>Network Monitor - \{csv_filename\}</title>',
        '<title>Network Monitor - {date_str} {hour:02d}:00</title>',
        content
    )

    # Update debug logging
    content = re.sub(
        r'f"\[DEBUG\] Navigation for: date=\{date_str\}, hour=\{hour\}, filename=\{csv_filename\}"',
        'f"[DEBUG] Navigation for: date={date_str}, hour={hour}"',
        content
    )

    if content != original_content:
        print("\n✅ Changes applied successfully!")
        print("\nWriting updated file...")
        with open('serve.py', 'w') as f:
            f.write(content)
        print("✅ serve.py has been refactored!")
        return True
    else:
        print("\n⚠️  No changes were made. File might already be refactored or patterns don't match.")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Refactoring serve.py to remove CSV filename concept")
    print("=" * 60)
    print()

    success = refactor_serve_py()

    if success:
        print("\n" + "=" * 60)
        print("✅ Refactoring complete!")
        print("=" * 60)
        print("\nNew URL format:")
        print("  - View: /view/2025-11-04/23")
        print("  - CSV:  /csv/2025-11-04/23")
        print("\nOld URL format (removed):")
        print("  - View: /view/2025-11-04/monitor_20251104_23.csv")
        print("  - CSV:  /csv/2025-11-04/monitor_20251104_23.csv")
    else:
        print("\n⚠️  Refactoring failed or already complete.")
