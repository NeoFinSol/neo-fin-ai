"""Setup file for neo-fin-ai project."""
from setuptools import setup, find_packages

setup(
    name="neo-fin-ai",
    version="1.0.0",
    description="NeoFin AI - Financial Analysis Tool",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn>=0.30.0",
        "pydantic>=2.8.0",
        "sqlalchemy>=2.0.30",
        "asyncpg>=0.29.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.0",
            "pytest-asyncio>=0.25.0",
            "black>=24.10.0",
            "flake8>=7.1.0",
        ],
    },
)
