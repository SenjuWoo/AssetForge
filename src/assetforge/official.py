"""Optional official Khronos glTF validation.

The validator is a Node package in .tools and is never installed automatically.
When it is absent the caller records NOT_TESTED rather than pretending the
structural checks are conformance checks.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import providers
from .util import run


def available(project=None) -> bool:
    return bool(providers.get("gltf-validator", project).get("available"))


def check(project, path: Path) -> dict:
    provider = providers.get("gltf-validator", project)
    if not provider.get("available"):
        return {
            "id": "GLB-014",
            "status": "NOT_TESTED",
            "detail": "official glTF validator is not installed",
        }
    details = provider.get("details") or {}
    command = [details["node"], details["wrapper"], details["module"], str(path)]
    result = run(command, timeout=120)
    if result.get("timed_out") or result["returncode"] != 0 or not result.get("stdout", "").strip():
        return {
            "id": "GLB-014",
            "status": "NOT_TESTED",
            "detail": (result.get("error") or result.get("stderr") or "validator produced no report")[-400:],
        }
    try:
        report = json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"id": "GLB-014", "status": "NOT_TESTED", "detail": "validator output was not JSON"}
    issues = report.get("issues") or {}
    errors = int(issues.get("numErrors", 0))
    warnings = int(issues.get("numWarnings", 0))
    if errors:
        status = "FAIL"
    elif warnings:
        status = "WARNING"
    else:
        status = "PASS"
    first = ""
    for message in (issues.get("messages") or [])[:3]:
        if message.get("severity") in (0, 1):
            first = f"; first: {message.get('code')} {message.get('message')}"
            break
    return {
        "id": "GLB-014",
        "status": status,
        "detail": f"official validator: {errors} error(s), {warnings} warning(s){first}",
    }
