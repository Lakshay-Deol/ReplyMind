"""Single source of truth for runtime paths.

Seven modules each did `RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR", "runtime"))`
at import time. Whichever of them was imported before webapp.py called
load_dotenv() captured the default instead of the configured value, so state
silently split across two directories: drafts landed in one, signals and the
community pulse in the other, and the dashboards read empty.

Loading .env here -- in a leaf module with no app dependencies -- means the
environment is populated before any caller resolves a path, and resolving
lazily means a test or a deployment can still override RUNTIME_DIR at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]

# Imported before any path is resolved, so RUNTIME_DIR from .env is always seen.
load_dotenv(dotenv_path=BASE_DIR / ".env")


def runtime_dir() -> Path:
    """The runtime root. Relative values resolve against the repo, not the CWD."""
    configured = os.getenv("RUNTIME_DIR", "runtime")
    path = Path(configured)
    return path if path.is_absolute() else BASE_DIR / path


def sub(*parts: str) -> Path:
    return runtime_dir().joinpath(*parts)


def memory_dir() -> Path:
    return sub("memory")


def signals_dir() -> Path:
    return sub("signals")


def opportunities_dir() -> Path:
    return sub("opportunities")


def triage_dir() -> Path:
    return sub("triage")


def activity_path() -> Path:
    return sub("activity.jsonl")


def metrics_path() -> Path:
    return sub("metrics.json")


def demo_comments_path() -> Path:
    return sub("demo_comments.json")
