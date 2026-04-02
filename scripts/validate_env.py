#!/usr/bin/env python3
"""
Environment validation script for NeoFin AI.

This script validates that all required environment variables are set
before starting the application in production mode.

Usage:
    python scripts/validate_env.py [--dev]

Options:
    --dev    Skip validation (development mode)

Exit codes:
    0 - All validations passed
    1 - Validation failed (missing required variables)
"""
import os
import sys
from pathlib import Path


def check_env_file() -> bool:
    """Check if .env file exists."""
    env_file = Path(__file__).parents[1] / ".env"
    if not env_file.exists():
        print("❌ .env file not found!")
        print("   Create .env file from .env.example:")
        print("   cp .env.example .env")
        return False
    print("✅ .env file exists")
    return True


def check_required_vars() -> bool:
    """Check required environment variables."""
    required_vars = [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print()
        print("   Set these variables in your .env file or environment.")
        return False

    print("✅ All required environment variables are set")
    return True


def check_weak_passwords() -> bool:
    """Check for weak/default passwords."""
    weak_passwords = ["postgres", "password", "admin", "123456"]
    password = os.getenv("POSTGRES_PASSWORD", "")

    if password.lower() in weak_passwords:
        print("⚠️  WARNING: Weak password detected for PostgreSQL!")
        print("   Consider using a stronger password:")
        print('   python -c "import secrets; print(secrets.token_urlsafe(32))"')
        return False

    print("✅ PostgreSQL password appears strong")
    return True


def check_api_key() -> bool:
    """Check API_KEY configuration."""
    api_key = os.getenv("API_KEY")
    dev_mode = os.getenv("DEV_MODE", "0") == "1"

    if dev_mode:
        print("ℹ️  DEV_MODE is enabled - authentication disabled")
        print("   ⚠️  Do not use DEV_MODE in production!")
        return True

    if not api_key:
        print("❌ API_KEY not set and DEV_MODE is not enabled")
        print("   Either set API_KEY or enable DEV_MODE for development:")
        print("   API_KEY=your-key-here")
        print("   or")
        print("   DEV_MODE=1")
        return False

    if len(api_key) < 16:
        print("⚠️  WARNING: API_KEY is too short (less than 16 characters)")
        print("   Consider using a longer key:")
        print('   python -c "import secrets; print(secrets.token_urlsafe(32))"')
        return False

    print("✅ API_KEY is configured")
    return True


def check_database_url() -> bool:
    """Check DATABASE_URL configuration."""
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("❌ DATABASE_URL not set")
        return False

    # Check for unexpanded variable interpolation
    if "${" in db_url:
        print("❌ DATABASE_URL contains unexpanded variable interpolation")
        print(f"   Current value: {db_url}")
        print("   This suggests variable interpolation is not working.")
        return False

    print("✅ DATABASE_URL is configured")
    return True


def main() -> int:
    """Run all validations."""
    print("=" * 60)
    print("NeoFin AI Environment Validation")
    print("=" * 60)
    print()

    # Check if --dev flag is passed
    if "--dev" in sys.argv:
        print("ℹ️  Development mode - skipping validation")
        return 0

    # Check if TESTING or CI mode
    if os.getenv("TESTING") == "1" or os.getenv("CI") == "1":
        print("ℹ️  Testing/CI mode - skipping validation")
        return 0

    # Check if DEV_MODE is enabled
    if os.getenv("DEV_MODE") == "1":
        print("ℹ️  DEV_MODE enabled - running in development mode")
        print()

    all_passed = True

    # Run checks
    all_passed &= check_env_file()
    print()

    all_passed &= check_required_vars()
    print()

    all_passed &= check_database_url()
    print()

    all_passed &= check_api_key()
    print()

    all_passed &= check_weak_passwords()
    print()

    print("=" * 60)
    if all_passed:
        print("✅ All validations passed!")
        return 0
    else:
        print("❌ Some validations failed!")
        print()
        print("Fix the issues above before running the application.")
        print("For development, you can use:")
        print("  - DEV_MODE=1 to bypass authentication")
        print("  - --dev flag to skip validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
