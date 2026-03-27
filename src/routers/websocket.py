import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.core.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for receiving real-time updates for a specific task.
    """
    await ws_manager.connect(websocket, task_id)
    try:
        while True:
            # We don't expect messages from client, but keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)
    except Exception as exc:
        logger.error(f"Error in websocket for task {task_id}: {exc}")
        ws_manager.disconnect(websocket, task_id)
