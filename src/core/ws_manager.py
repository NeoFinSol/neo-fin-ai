import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections for real-time task updates.
    Supports grouping connections by task_id.
    """
    def __init__(self):
        # Maps task_id to a set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept connection and add to the task group."""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        self.active_connections[task_id].add(websocket)
        logger.info(f"WebSocket connected for task {task_id}. Total connections for task: {len(self.active_connections[task_id])}")

    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove connection from the task group."""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
            logger.info(f"WebSocket disconnected for task {task_id}")

    async def broadcast(self, task_id: str, message: dict):
        """Broadcast JSON message to all connections subscribed to a task_id."""
        if task_id not in self.active_connections:
            return

        dead_connections = set()
        for connection in self.active_connections[task_id]:
            try:
                await connection.send_json(message)
            except Exception as exc:
                logger.warning(f"Failed to send message to WS for task {task_id}: {exc}")
                dead_connections.add(connection)
        
        # Cleanup broken connections
        for dead in dead_connections:
            self.disconnect(dead, task_id)

# Singleton instance
ws_manager = ConnectionManager()
