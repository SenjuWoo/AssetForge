"""Reach a ComfyUI backend for comfy-forge work.

comfy-forge owns ComfyUI, its models and its music generator. AssetForge only
needs an API to send the job to. A running backend is used as is: a standalone
ComfyUI on 8188, or SwarmUI's own backend on 7820-7832 (the ports comfy-forge's
`image-stack.ps1` checks). When none answers and the recipe allows it,
AssetForge starts comfy-forge's ComfyUI headless on a free local port for that
one job and stops it afterwards.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from .util import _RawCommand, _windows_shim, run

PORTS = (8188, *range(7820, 7833))


class BackendError(RuntimeError):
    pass


def _alive(url: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"{url}/system_stats", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return data if isinstance(data, dict) and data.get("system") else None


def find_running(explicit: str = "") -> tuple[str, dict] | None:
    """The first ComfyUI API that answers: COMFYUI_URL, then the ports
    comfy-forge knows. An explicit URL (the recipe's `url`) is the only
    candidate: when it does not answer that is an error, not a reason to send
    the job to some other server."""
    explicit = (explicit or "").strip().rstrip("/")
    if explicit:
        stats = _alive(explicit)
        if not stats:
            raise BackendError(f"no ComfyUI answered at {explicit} (the url you set); start it or leave url empty")
        return explicit, stats
    candidates = [os.environ.get("COMFYUI_URL", "")]
    candidates += [f"http://127.0.0.1:{port}" for port in PORTS]
    for url in candidates:
        url = url.strip().rstrip("/")
        if not url:
            continue
        stats = _alive(url)
        if stats:
            return url, stats
    return None


def comfy_python(root: Path) -> Path:
    """Ask comfy-forge which interpreter its ComfyUI uses (`image-stack.ps1
    python`), so AssetForge never guesses the install."""
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise BackendError("PowerShell is required to ask comfy-forge for its ComfyUI")
    result = run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "TOOLS" / "image-stack.ps1"), "python"],
                 timeout=120, cwd=root)
    for line in reversed((result.get("stdout") or "").splitlines()):
        candidate = Path(line.strip().strip('"'))
        if line.strip() and candidate.suffix.lower() in (".exe", "") and candidate.is_file():
            return candidate
    raise BackendError("comfy-forge found no ComfyUI interpreter (`image-stack.ps1 python`); install ComfyUI or SwarmUI through comfy-forge")


def comfy_root(python: Path) -> Path:
    """ComfyUI's folder beside the interpreter: the portable layout keeps
    python_embeded next to ComfyUI; a venv sits inside it."""
    for candidate in (python.parent.parent / "ComfyUI", python.parent.parent.parent, python.parent.parent):
        if (candidate / "main.py").is_file() and (candidate / "comfy").is_dir():
            return candidate
    raise BackendError(f"no ComfyUI main.py next to {python}")


SWARM_PORT = re.compile(r"^\s*Port\s*:\s*(\d+)", re.M)


def swarm_root(root: Path) -> Path:
    """The SwarmUI folder comfy-forge uses: the one above its ComfyUI
    interpreter that holds the launcher."""
    python = comfy_python(root)
    for parent in python.parents:
        if (parent / "launch-windows.bat").is_file() or (parent / "launch-linux.sh").is_file():
            return parent
    raise BackendError(f"no SwarmUI launcher above {python}; comfy-forge renders images through SwarmUI")


def swarm_port(folder: Path) -> int:
    """The web port in SwarmUI's settings (7801 when unset), read the way
    comfy-forge reads it."""
    try:
        match = SWARM_PORT.search((folder / "Data" / "Settings.fds").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        match = None
    return int(match.group(1)) if match else 7801


def swarm_alive(port: int, timeout: float = 4.0) -> bool:
    request = urllib.request.Request(f"http://127.0.0.1:{int(port)}/API/GetNewSession", data=b"{}",
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, ValueError, urllib.error.URLError):
        return False
    return isinstance(data, dict) and bool(data.get("session_id"))


@contextmanager
def swarm(root: Path, mode: str, log_path: Path, startup_timeout: float = 420):
    """Yield (port, how) for one image job. `port` is 0 when comfy-forge's own
    SwarmUI already answers, so its settings are used untouched. Otherwise, in
    'auto' or 'start' mode, SwarmUI is started without a browser on a free
    port and stopped when the job ends."""
    if mode not in ("auto", "running", "start"):
        raise BackendError("backend must be auto, running or start")
    folder = swarm_root(root)
    if mode in ("auto", "running"):
        port = swarm_port(folder)
        if swarm_alive(port):
            yield 0, f"running SwarmUI on port {port}"
            return
        if mode == "running":
            raise BackendError(f"SwarmUI is not answering on port {port}; start it, or use --set backend=auto")
    launcher = folder / ("launch-windows.bat" if sys.platform == "win32" else "launch-linux.sh")
    if not launcher.is_file():
        raise BackendError(f"no SwarmUI launcher for this system in {folder}")
    port = _free_port()
    argv = _windows_shim([str(launcher), "--launch_mode", "none", "--port", str(port)])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        proc = subprocess.Popen(argv.line() if isinstance(argv, _RawCommand) else argv, cwd=folder,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        try:
            deadline = time.time() + startup_timeout
            while time.time() < deadline:
                if proc.poll() is not None:
                    raise BackendError(f"SwarmUI exited during startup (code {proc.returncode}); see {log_path}")
                if swarm_alive(port, timeout=2.0):
                    break
                time.sleep(1.0)
            else:
                raise BackendError(f"SwarmUI did not answer within {startup_timeout:g}s; see {log_path}")
            yield port, f"temporary SwarmUI from {folder} on port {port}, stopped after the job"
        finally:
            _stop(proc)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        # ComfyUI can spawn helpers; /T ends the whole tree.
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


@contextmanager
def backend(root: Path, mode: str, log_path: Path, startup_timeout: float = 240, explicit: str = ""):
    """Yield (url, how) for one job. mode: 'auto' uses a running backend or
    starts a temporary one; 'running' needs one already up; 'start' always
    starts a temporary one."""
    if mode not in ("auto", "running", "start"):
        raise BackendError("backend must be auto, running or start")
    if mode in ("auto", "running"):
        found = find_running(explicit)
        if found:
            yield found[0], f"running ComfyUI {found[1]['system'].get('comfyui_version', '')} at {found[0]}"
            return
        if mode == "running":
            raise BackendError("no ComfyUI answered on 8188 or 7820-7832; start SwarmUI or ComfyUI, or use --set backend=auto")
    python = comfy_python(root)
    folder = comfy_root(python)
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        proc = subprocess.Popen([str(python), "-s", "main.py", "--listen", "127.0.0.1", "--port", str(port), "--disable-auto-launch"],
                                cwd=folder, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        try:
            deadline = time.time() + startup_timeout
            stats = None
            while time.time() < deadline:
                if proc.poll() is not None:
                    raise BackendError(f"ComfyUI exited during startup (code {proc.returncode}); see {log_path}")
                stats = _alive(url)
                if stats:
                    break
                time.sleep(1.0)
            if not stats:
                raise BackendError(f"ComfyUI did not answer within {startup_timeout:g}s; see {log_path}")
            yield url, f"temporary ComfyUI {stats['system'].get('comfyui_version', '')} from {folder}, stopped after the job"
        finally:
            _stop(proc)
