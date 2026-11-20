"""Load config.toml from the project root.

Usage:
    from pipeline.config import CONFIG
    CONFIG["gcp"]["bucket"]
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "config.toml", "rb") as f:
    CONFIG = tomllib.load(f)
