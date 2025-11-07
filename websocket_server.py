#!/usr/bin/env python3

"""
WebSocket server for real-time network monitoring updates.
"""

import asyncio
import websockets
import json


# Global WebSocket clients
websocket_clients = set()


async def websocket_handler(websocket):
    """Handle WebSocket connections for real-time updates."""
    global websocket_clients
    websocket_clients.add(websocket)
    print(f"[+] WebSocket client connected ({len(websocket_clients)} total)")

    try:
        # Send initial greeting
        await websocket.send(
            json.dumps(
                {
                    "type": "connected",
                    "message": "WebSocket connected - awaiting real-time updates",
                }
            )
        )

        # Keep connection alive
        async for message in websocket:
            pass  # Client messages not currently handled
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        websocket_clients.remove(websocket)
        print(f"[-] WebSocket client disconnected ({len(websocket_clients)} remaining)")


async def broadcast_update(db):
    """Broadcast latest data to all connected WebSocket clients every 30 seconds."""
    while True:
        await asyncio.sleep(30)  # 30 second batches

        if websocket_clients:
            # Get latest log entry
            latest = db.get_latest_log()

            if latest:
                (
                    timestamp,
                    status,
                    response_time,
                    success_count,
                    total_count,
                    failed_count,
                ) = latest

                # Prepare update message
                update = {
                    "type": "update",
                    "data": {
                        "timestamp": timestamp,
                        "status": status,
                        "response_time": response_time,
                        "success_count": success_count,
                        "total_count": total_count,
                        "failed_count": failed_count,
                    },
                }

                # Broadcast to all clients
                websockets.broadcast(websocket_clients, json.dumps(update))
                print(f"[*] Broadcast update to {len(websocket_clients)} client(s)")


async def start_websocket_server(db, port=8081):
    """Start WebSocket server."""
    async with websockets.serve(websocket_handler, "0.0.0.0", port):
        print(f"[*] WebSocket server started on port {port}")
        # Start broadcast task
        await broadcast_update(db)
