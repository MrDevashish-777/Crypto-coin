#!/usr/bin/env python3
"""Preflight checks for Apple Silicon Mac (M1–M4) local advisor setup."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def main() -> int:
    print("CoinDCX Advisor — Mac preflight\n")
    errors = 0

    machine = platform.machine()
    if machine == "arm64":
        ok(f"CPU architecture: {machine} (Apple Silicon)")
    else:
        warn(f"CPU architecture: {machine} (not arm64; stack still may work)")

    py = sys.version_info
    if py >= (3, 11):
        ok(f"Python {py.major}.{py.minor}.{py.micro}")
    elif py >= (3, 9):
        warn(f"Python {py.major}.{py.minor} — use 3.11+ on Mac (brew install python@3.12)")
    else:
        fail(f"Python {py.major}.{py.minor} — need 3.9+")
        errors += 1

    try:
        import fastapi  # noqa: F401
        import motor  # noqa: F401
        import numpy  # noqa: F401
        import pandas  # noqa: F401

        ok("Core packages import (fastapi, motor, numpy, pandas)")
    except ImportError as exc:
        fail(f"Missing package: {exc}. Run: pip install -r requirements.txt")
        errors += 1

    env_path = ROOT / ".env"
    if env_path.is_file():
        text = env_path.read_text(encoding="utf-8")
        if "DATABASE_URL=postgresql" in text:
            warn(".env still has DATABASE_URL (PostgreSQL) — remove it; advisor uses MongoDB only")
        if "CHART_RENDERER=playwright" in text.lower():
            warn("CHART_RENDERER=playwright — on Mac prefer matplotlib unless Playwright is installed")
        else:
            ok(".env present")
    else:
        warn(".env missing — copy from .env.example")

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            ok("Ollama CLI reachable")
            if "plutus" in result.stdout.lower():
                ok("Plutus model appears in ollama list")
            else:
                warn("Plutus not listed — run: ollama pull 0xroyce/plutus")
        else:
            warn("Ollama installed but `ollama list` failed")
    except FileNotFoundError:
        warn("Ollama not in PATH — install: brew install ollama && brew services start ollama")
    except subprocess.TimeoutExpired:
        warn("Ollama list timed out")

    print()
    if errors:
        print(f"Finished with {errors} error(s). Fix FAIL items before running the server.")
        return 1
    print("Preflight complete. Start with: python scripts/run_server.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
