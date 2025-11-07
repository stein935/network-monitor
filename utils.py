#!/usr/bin/env python3

"""
Utility functions for the network monitor server.
"""

from pathlib import Path
import webbrowser
import time


def get_version():
    """Read version from VERSION file."""
    try:
        version_file = Path(__file__).parent / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
    except Exception:
        pass
    return "1.0.0"  # Fallback version


def format_bytes(kb):
    """
    Convert kilobytes to human-readable format.

    Args:
        kb: Size in kilobytes

    Returns:
        str: Human-readable size (e.g., "45.2MB")
    """
    bytes_val = kb * 1024
    if bytes_val < 1024:
        return f"{bytes_val}B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f}KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f}MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f}GB"


def open_browser(url, delay=1):
    """
    Open browser after a short delay.

    Args:
        url: URL to open
        delay: Seconds to wait before opening (default: 1)
    """
    time.sleep(delay)
    webbrowser.open(url)
