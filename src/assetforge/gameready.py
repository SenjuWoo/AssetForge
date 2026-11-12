"""Triangle and texture caps for one generated prop.

Engines count triangles. A quad is two. The default cap is 20,000 triangles:
the Roblox MeshPart ceiling (Creator Hub general specifications, updated
2026-11-11) and the handheld-prop ceiling used here for Unity, Godot and
Unreal, which publish no single axe number. hero (30,000) is a close-up
override and is not a Roblox mesh. accessory (4,000) is the Roblox worn
accessory ceiling (rigid accessory specifications, updated 2026-06-16).

A 700,000-triangle file is a sculpt. It is not a budget, and it does not ship.
"""

from __future__ import annotations

# Ask Blender for this fraction of the cap. Collapse can land a little over the
# ratio; the written file is still rejected above the cap.
# shortcut: 85% is headroom, not a second budget. Change it only after a real
# export shows the overshoot no longer fits under the cap.
HEADROOM_PERCENT = 85

BUDGETS = {
    "game": {"tris": 20_000, "texture": 1024},
    "hero": {"tris": 30_000, "texture": 2048},
    "accessory": {"tris": 4_000, "texture": 1024},
}


def resolve_budget(budget: str, tris: int, texture: int) -> tuple[int, int, int]:
    """Return (blender_target, texture_cap, hard_cap).

    tris 0 asks Blender for 85% of the cap. An explicit tris above the cap is
    rejected, so a sculpt count cannot be passed in as an override. texture 0
    uses the budget. A larger texture request is clamped to the budget.
    """
    name = str(budget or "").strip()
    row = BUDGETS.get(name)
    if row is None:
        names = ", ".join(BUDGETS)
        raise ValueError(f"budget must be one of {names}")
    if tris < 0 or texture < 0:
        raise ValueError("tris and texture must be zero or positive")
    if tris and tris < 50:
        raise ValueError("tris must be at least 50, or 0 to use the budget")
    if texture and not 64 <= texture <= 8192:
        raise ValueError("texture must be 0 or between 64 and 8192")
    hard_cap = int(row["tris"])
    if tris > hard_cap:
        raise ValueError(
            f"{tris} triangles is over the {name} cap of {hard_cap}. "
            "A raw sculpt does not ship. Leave tris at 0."
        )
    target = int(tris) if tris else hard_cap * HEADROOM_PERCENT // 100
    cap = int(texture or row["texture"])
    return target, min(cap, int(row["texture"])), hard_cap


def reject_over_cap(triangles: int, cap: int, budget: str) -> None:
    """Fail when the written mesh is over the budget. Equal to the cap passes."""
    if int(triangles) > int(cap):
        raise ValueError(
            f"{int(triangles)} triangles is over the {budget} cap of {int(cap)}. "
            "This file is not game-ready."
        )


def fit_size(width: int, height: int, cap: int) -> tuple[int, int]:
    """Scale so the long edge is a power of two at or under cap. Leave smaller images alone."""
    width = int(width)
    height = int(height)
    longest = max(width, height)
    if longest <= 0 or cap <= 0 or longest <= cap:
        return width, height
    limit = min(longest, int(cap))
    pot = 1
    while pot * 2 <= limit:
        pot *= 2
    factor = pot / longest
    return max(1, int(round(width * factor))), max(1, int(round(height * factor)))
