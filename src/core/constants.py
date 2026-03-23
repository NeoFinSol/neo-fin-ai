"""
Core constants for the NeoFin AI application.

This module contains shared constants used across the application
to avoid duplication and ensure consistency.
"""

# PDF validation constants
PDF_MAGIC_HEADER = b"%PDF-"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_FILE_SIZE_MB = MAX_FILE_SIZE // (1024 * 1024)

# Maximum number of pages to process in a single PDF
# Prevents DoS attacks via multi-page PDFs
MAX_PDF_PAGES = 100  # 100 pages limit

# Magic header size for quick validation
MAGIC_HEADER_SIZE = 8  # Read first 8 bytes for magic number check

# Retry configuration
DEFAULT_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF = 2.0  # multiplier

# Timeout configuration (seconds)
DEFAULT_TIMEOUT = 120
CONNECTION_TIMEOUT = 30
READ_TIMEOUT = 90
