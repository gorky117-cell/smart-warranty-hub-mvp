from typing import Dict

from ..models import RiskScore
from ..storage import store


def compute_risk(user_id: str, warranty_id: str) -> RiskScore:
    events = store.get_behaviour_events(user_id, warranty_id)
    warranty = store.warranties.get(warranty_id)

    base = 0.35
    factors: Dict[str, float] = {}

    dismisses = len([e for e in events if e.event_type == "nudge_dismissed"])
    if dismisses:
        bump = min(0.05 * dismisses, 0.25)
        factors["dismissed_nudges"] = bump
        base += bump

    completions = len([e for e in events if e.event_type == "task_completed"])
    if completions:
        bump = -min(0.03 * completions, 0.15)
        factors["recent_care"] = bump
        base += bump

    reported_issue = len([e for e in events if e.event_type == "issue_reported"])
    if reported_issue:
        bump = min(0.1 * reported_issue, 0.3)
        factors["recent_issue"] = bump
        base += bump

    if warranty and warranty.expiry_date:
        factors["expiry_known"] = -0.05
        base -= 0.05

    value = max(0.0, min(base, 1.0))
    if value >= 0.75:
        band = "high"
    elif value >= 0.5:
        band = "medium"
    else:
        band = "low"

    return RiskScore(
        warranty_id=warranty_id,
        user_id=user_id,
        value=round(value, 2),
        band=band,
        contributors=factors,
    )
