#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FREQUENCY=${1:-1}
SAMPLE_SIZE=${2:-5}
LOG_RETENTION_DAYS=10

echo "[*] Starting network monitor daemon..."
echo "[*] Frequency: ${FREQUENCY}s, Sample size: ${SAMPLE_SIZE}"
echo "[*] Log retention: ${LOG_RETENTION_DAYS} days"
echo "[*] Press Ctrl+C to stop"
echo ""

# Function to clean up old log directories (older than LOG_RETENTION_DAYS)
cleanup_old_logs() {
	local CUTOFF_DATE=$(date -d "${LOG_RETENTION_DAYS} days ago" +%Y-%m-%d 2>/dev/null || date -v-${LOG_RETENTION_DAYS}d +%Y-%m-%d)

	# Find and remove old log directories
	find "$SCRIPT_DIR/logs" -maxdepth 1 -type d -name "20*" | while read -r dir; do
		local DIR_DATE=$(basename "$dir")
		if [[ "$DIR_DATE" < "$CUTOFF_DATE" ]]; then
			echo "[*] Removing old logs: $DIR_DATE"
			rm -rf "$dir"
		fi
	done
}

# Function to get current hour's log file (includes date directory creation)
get_log_file() {
	local LOG_DIR="$SCRIPT_DIR/logs/$(date +%Y-%m-%d)"
	local CSV_DIR="$LOG_DIR/csv"
	mkdir -p "$CSV_DIR"
	echo "$CSV_DIR/monitor_$(date +%Y%m%d_%H).csv"
}

# Initialize the first log file
LOG_FILE=$(get_log_file)
if [ ! -f "$LOG_FILE" ]; then
	echo "timestamp, status, response_time, success_count, total_count, failed_count" >"$LOG_FILE"
fi

# Arrays to store samples
declare -a response_times
sample_count=0

# Track last cleanup time
LAST_CLEANUP=$(date +%s)
CLEANUP_INTERVAL=3600 # Clean up once per hour

# Initial cleanup on start
cleanup_old_logs

# Run forever
while true; do
	ITERATION_START=$(date +%s)

	# Check if it's time to cleanup (once per hour)
	if [ $((ITERATION_START - LAST_CLEANUP)) -ge $CLEANUP_INTERVAL ]; then
		cleanup_old_logs
		LAST_CLEANUP=$ITERATION_START
	fi

	PING_RESULT=$(ping -c 1 -W 1 8.8.8.8 2>&1)
	if echo "$PING_RESULT" | grep -q "1 packets received\|1 received"; then
		# Extract avg response time (works on both macOS and Linux)
		# macOS format: round-trip min/avg/max/stddev = 14.123/15.456/16.789/1.234 ms
		# Linux format: rtt min/avg/max/mdev = 14.123/15.456/16.789/1.234 ms
		RESPONSE_TIME=$(echo "$PING_RESULT" | grep -oE '(round-trip|rtt) [^=]*= [0-9]+\.[0-9]+/[0-9]+\.[0-9]+' | grep -oE '/[0-9]+\.[0-9]+' | head -1 | sed 's/\///')
		response_times[$sample_count]=$RESPONSE_TIME
	else
		response_times[$sample_count]="null"
	fi

	sample_count=$((sample_count + 1))

	# Log average after collecting SAMPLE_SIZE samples
	if [ "$sample_count" -ge "$SAMPLE_SIZE" ]; then
		# Check if we need to switch to a new hourly log file
		CURRENT_LOG_FILE=$(get_log_file)
		if [ "$CURRENT_LOG_FILE" != "$LOG_FILE" ]; then
			LOG_FILE="$CURRENT_LOG_FILE"
			# Create header if new file
			if [ ! -f "$LOG_FILE" ]; then
				echo "timestamp, status, response_time, success_count, total_count, failed_count" >"$LOG_FILE"
			fi
		fi

		# Calculate average response time (excluding disconnects)
		total=0
		count=0
		for time in "${response_times[@]}"; do
			if [ "$time" != "null" ]; then
				total=$(echo "$total + $time" | bc)
				count=$((count + 1))
			fi
		done

		# Check connection status (if any were connected)
		if [ "$count" -gt 0 ]; then
			avg=$(echo "scale=3; $total / $count" | bc)
			echo "$(date '+%Y-%m-%d %H:%M:%S'), CONNECTED, ${avg}, ${count}, ${SAMPLE_SIZE}, $((SAMPLE_SIZE - count))" >>"$LOG_FILE"
		else
			echo "$(date '+%Y-%m-%d %H:%M:%S'), DISCONNECTED, null, 0, ${SAMPLE_SIZE}, ${SAMPLE_SIZE}" >>"$LOG_FILE"
		fi

		# Reset arrays
		response_times=()
		sample_count=0
	fi

	# Calculate time elapsed and adjust sleep to maintain precise frequency
	ITERATION_END=$(date +%s)
	ELAPSED=$((ITERATION_END - ITERATION_START))
	SLEEP_TIME=$((FREQUENCY - ELAPSED))

	if [ "$SLEEP_TIME" -gt 0 ]; then
		sleep "$SLEEP_TIME"
	fi
done
