import hmac

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.core.ws_manager import ws_manager
from src.models.settings import app_settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])

# RFC 6455 §7.4.2 — application-defined close code for "Unauthorized"
_WS_CLOSE_UNAUTHORIZED: int = 4001


def _is_ws_auth_valid(api_key: str | None) -> bool:
    """Return True if the provided api_key is valid for the current settings."""
    if app_settings.dev_mode:
        return True
    if not app_settings.api_key:
        return True
    if not api_key:
        return False
    try:
        return hmac.compare_digest(
            api_key.encode("utf-8"),
            app_settings.api_key.encode("utf-8"),
        )
    except (UnicodeEncodeError, AttributeError):
        return False


@router.websocket("/{task_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    api_key: str | None = Query(default=None, alias="api_key"),
) -> None:
    """
    WebSocket endpoint for receiving real-time updates for a specific task.

    Authentication: pass the API key as ?api_key=<key> query parameter.
    Browser WebSocket clients cannot set custom headers, so query param is used.
    Rejected connections are closed with code 4001 (Unauthorized).
    """
    if not _is_ws_auth_valid(api_key):
        reason = "missing api_key" if not api_key else "invalid api_key"
        logger.warning("WebSocket auth rejected: task_id=%s reason=%s", task_id, reason)
        await websocket.close(code=_WS_CLOSE_UNAUTHORIZED)
        return

    await ws_manager.connect(websocket, task_id)
    try:
        while True:
            # We don't expect messages from client, but keep the connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, task_id)
    except Exception as exc:
        logger.error("WebSocket error: task_id=%s error=%s", task_id, exc)
        ws_manager.disconnect(websocket, task_id)
