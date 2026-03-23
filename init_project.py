#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NeoFin AI Project Initialization Script
Automatically configures the project for development
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def run_command(cmd, description=None):
    """Execute command and handle errors"""
    if description:
        print(f"\n{'='*60}")
        print(f"[*] {description}")
        print('='*60)

    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=False)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[-] Error: {e}")
        return False


def check_python():
    """Check if Python is installed"""
    print("\n[*] Checking Python...")
    try:
        result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
        print(f"[+] {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"[-] Python not found: {e}")
        return False


def create_venv():
    """Create virtual environment"""
    env_path = Path("env")

    if env_path.exists():
        print("\n[+] Virtual environment already exists")
        return True

    print("\n[*] Creating virtual environment...")
    return run_command(
        f"{sys.executable} -m venv env",
        "Creating virtual environment"
    )


def install_dependencies():
    """Install dependencies"""
    pip_cmd = sys.executable if platform.system() == "Windows" else "python3"

    # Update pip
    run_command(
        f"{pip_cmd} -m pip install --upgrade pip",
        "Updating pip"
    )

    # Install requirements.txt
    if not run_command(
        f"{pip_cmd} -m pip install -r requirements.txt --no-cache-dir",
        "Installing production dependencies"
    ):
        return False

    # Install requirements-dev.txt
    if not run_command(
        f"{pip_cmd} -m pip install -r requirements-dev.txt --no-cache-dir",
        "Installing development dependencies"
    ):
        return False

    return True


def verify_installation():
    """Verify installation success"""
    print("\n" + "="*60)
    print("[*] Verifying installation")
    print("="*60)

    checks = [
        ("pytest", "python -m pytest --version"),
        ("fastapi", "python -c 'import fastapi; print(fastapi.__version__)'"),
        ("sqlalchemy", "python -c 'import sqlalchemy; print(sqlalchemy.__version__)'"),
        ("pydantic", "python -c 'import pydantic; print(pydantic.__version__)'"),
    ]

    all_ok = True
    for name, cmd in checks:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"[+] {name}: {result.stdout.strip()}")
            else:
                print(f"[-] {name}: not installed")
                all_ok = False
        except Exception as e:
            print(f"[-] {name}: error - {e}")
            all_ok = False

    return all_ok


def print_next_steps():
    """Print next steps"""
    print("\n" + "="*60)
    print("[+] Initialization completed!")
    print("="*60)
    print("\n[*] Next steps:\n")
    
    if platform.system() == "Windows":
        print("1) Activate virtual environment:")
        print("   .\\env\\Scripts\\Activate.ps1\n")
    else:
        print("1) Activate virtual environment:")
        print("   source env/bin/activate\n")

    print("2) Run the application:")
    print("   python src/app.py\n")

    print("3) Or run tests:")
    print("   python -m pytest tests/ -v\n")

    print("Read more: BUILD_GUIDE.md")


def main():
    """Main function"""
    print("\n" + "="*60)
    print("[*] NeoFin AI - Project Initialization")
    print("="*60)
    
    # Checks
    if not check_python():
        sys.exit(1)

    if not create_venv():
        sys.exit(1)

    if not install_dependencies():
        sys.exit(1)

    if not verify_installation():
        print("\n[-] Some components are not installed, but project may work")

    print_next_steps()
    print()


if __name__ == "__main__":
    main()
