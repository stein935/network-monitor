#!/usr/bin/env bash

# Wrapper script to run the visualization with the virtual environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Run the visualization script
python "$SCRIPT_DIR/visualize.py" "$@"

# Deactivate when done
deactivate
