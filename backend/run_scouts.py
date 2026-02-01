#!/usr/bin/env python3
"""
Entry point for running the Scout layer.

Usage:
    python run_scouts.py

Environment variables (can be set in .env file or environment):
    OPENAI_API_KEY: Required. Your OpenAI API key.
    SCOUT_INTERVAL_SECONDS: Optional. Seconds between cycles (default: 300).
    SCOUT_MODEL: Optional. OpenAI model to use (default: gpt-5-nano).
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from parent directory (project root)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Also try loading from current directory
    load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scout.engine import main

if __name__ == "__main__":
    asyncio.run(main())
