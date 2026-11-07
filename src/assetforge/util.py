"""Shared helpers: hashing, atomic JSON, slugs and subprocess execution.

Every external command in AssetForge goes through `run()` so arguments stay a
list (never a shell string), output is captured, and a timeout can never hang a
job. Windows .bat/.cmd shims are invoked through cmd.exe explicitly.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    """Write JSON via a sibling temp file so a crash never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def slugify(text: str, fallback: str = "asset") -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return value[:48] or fallback


def safe_name(text: str, fallback: str = "asset") -> str:
    """Asset ids become directory names, so keep them to a strict alphabet."""
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip(".-")
    return value[:72] or fallback


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def which(name: str):
    import shutil

    return shutil.which(name)


def _windows_shim(cmd):
    if sys.platform == "win32" and cmd:
        first = str(cmd[0]).lower()
        if first.endswith((".bat", ".cmd")):
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            # cmd.exe re-parses its command line; pass one quoted string so paths
            # with spaces stay intact and arguments are not re-split.
            line = subprocess.list2cmdline([str(part) for part in cmd])
            return [comspec, "/d", "/s", "/c", line]
    return [str(part) for part in cmd]


def run(cmd, timeout: float = 120, cwd: Path | str | None = None, env: dict | None = None) -> dict:
    """Run a command with list arguments. Returns a result dict, never raises on
    a non-zero exit; callers decide what an exit code means."""
    argv = _windows_shim(cmd)
    merged = dict(os.environ)
    if env:
        merged.update(env)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            env=merged,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
        return {
            "cmd": argv,
            "returncode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": argv,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
            "error": f"timed out after {timeout:g}s",
        }
    except OSError as exc:
        return {
            "cmd": argv,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "error": str(exc),
        }


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def clamp_int(value, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
