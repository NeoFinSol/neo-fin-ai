#!/usr/bin/env python3
"""CLI entrypoint for NeoFin AI bounded cleanup jobs."""

from src.maintenance.admin_cleanup import main


if __name__ == "__main__":
    raise SystemExit(main())
