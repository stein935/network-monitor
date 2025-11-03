#!/usr/bin/env bash

# Wrapper script to run the live visualization server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if running in Docker (system packages available)
if [ -f "/.dockerenv" ]; then
	# In Docker - use system python3 with system packages
	echo "[*] Running in Docker with system packages..."
	python3 "$SCRIPT_DIR/serve.py" "$@"
else
	# Native environment - use venv
	# Check if venv exists, if not create it
	if [ ! -d "$SCRIPT_DIR/venv" ]; then
		echo "[*] Creating virtual environment..."
		python3 -m venv "$SCRIPT_DIR/venv"
		source "$SCRIPT_DIR/venv/bin/activate"
		pip install -r "$SCRIPT_DIR/requirements.txt"
	else
		# Activate virtual environment
		source "$SCRIPT_DIR/venv/bin/activate"
	fi

	# Run the server
	python "$SCRIPT_DIR/serve.py" "$@"

	# Deactivate when done
	deactivate
fi
