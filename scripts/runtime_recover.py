#!/usr/bin/env python3
"""CLI entrypoint for NeoFin AI runtime stale recovery."""

from src.maintenance.admin_runtime_recovery import main


if __name__ == "__main__":
    raise SystemExit(main())
