import io
import logging
import os
from pathlib import Path, PurePath

logger = logging.getLogger(__name__)

def cleanup_temp_file(file_path: str | os.PathLike | io.IOBase | None) -> None:
    """
    Safely cleanup temporary file or file-like object.
    
    Supports:
    - str: File path
    - os.PathLike: Path object
    - io.IOBase: file-like objects (BytesIO, StringIO, open files)
    - None: No-op
    
    Args:
        file_path: Path to file or file-like object
    """
    if file_path is None:
        return
    
    # 1. File-like objects (BytesIO, StringIO, open files)
    if hasattr(file_path, 'close') and callable(getattr(file_path, 'close')):
        try:
            file_path.close()
            logger.debug("Closed file-like object: %s", type(file_path).__name__)
        except Exception as exc:
            logger.warning("Failed to close file-like object: %s", exc)
        return
    
    # 2. Path as str/Path/PathLike
    try:
        if isinstance(file_path, (str, PurePath)):
            path = Path(file_path)
        else:
            path = Path(str(file_path))
        
        if path.is_file():
            path.unlink(missing_ok=True)
            logger.debug("Deleted temporary file: %s", path)
    except (TypeError, OSError, ValueError) as exc:
        logger.warning("Failed to cleanup path %r: %s", file_path, type(exc).__name__)
