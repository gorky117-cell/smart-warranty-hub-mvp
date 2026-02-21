from typing import List

from ..models import Nudge, RiskScore
from ..storage import generate_id, store
from .warranty_status import compute_warranty_status


def _variant_copy(variant: str | None) -> dict:
    if variant == "B":
        return {
            "snapshot_title": "Coverage Quick View",
            "snapshot_msg": "Key terms, exclusions, and expiry at a glance.",
            "care_title": "Do It Now",
            "care_msg": "One-minute steps cut failure risk—do them now.",
            "expiry_title": "Use It Before You Lose It",
            "expiry_msg": "Coverage ending soon—log proofs and run checks.",
        }
    return {
        "snapshot_title": "Warranty Snapshot",
        "snapshot_msg": "Coverage and exclusions ready in one place for quick claims.",
        "care_title": "Preventive Care",
        "care_msg": "Complete quick maintenance steps to keep failure risk down.",
        "expiry_title": "Expiry Reminder",
        "expiry_msg": "Warranty ending—capture proofs and run checks now.",
    }


def generate_nudges(risk: RiskScore, variant: str | None = None) -> List[Nudge]:
    copy = _variant_copy(variant)
    warranty = store.warranties.get(risk.warranty_id)
    nudges: List[Nudge] = []

    if warranty:
        nudges.append(
            Nudge(
                id=generate_id("ndg"),
                warranty_id=risk.warranty_id,
                user_id=risk.user_id,
                title=copy["snapshot_title"],
                message=copy["snapshot_msg"],
                reason="Provide plain-language dashboard",
                suggested_actions=[
                    "Review coverage and exclusions now.",
                    "Upload invoice if missing.",
                ],
            )
        )

    if risk.band != "low":
        nudges.append(
            Nudge(
                id=generate_id("ndg"),
                warranty_id=risk.warranty_id,
                user_id=risk.user_id,
                title=copy["care_title"],
                message=copy["care_msg"],
                reason="Risk score indicates elevated probability; preventive care can reduce it.",
                suggested_actions=[
                    "Acknowledge or complete pending maintenance tasks.",
                    "Capture photos or logs if you notice anomalies.",
                ],
            )
        )

    if warranty:
        st = compute_warranty_status(
            purchase_date=getattr(warranty, "purchase_date", None),
            coverage_months=getattr(warranty, "coverage_months", None),
            expiry_date=getattr(warranty, "expiry_date", None),
        )
        days_left = st.get("days_left")
        if st.get("status") == "expired":
            lapse_text = st.get("lapsed_text") or "some time"
            nudges.append(
                Nudge(
                    id=generate_id("ndg"),
                    warranty_id=risk.warranty_id,
                    user_id=risk.user_id,
                    title="Coverage Lapsed",
                    message=f"Warranty lapsed {lapse_text} ago. Standard claim is likely not eligible.",
                    reason="Coverage window expired",
                    suggested_actions=[
                        "Contact OEM support for goodwill or paid repair options.",
                        "Upload invoice and service history for exception review.",
                    ],
                )
            )
        elif isinstance(days_left, int) and days_left < 60:
            nudges.append(
                Nudge(
                    id=generate_id("ndg"),
                    warranty_id=risk.warranty_id,
                    user_id=risk.user_id,
                    title=copy["expiry_title"],
                    message=f"Warranty ends in {days_left} days. Capture proofs and run checks now.",
                    reason="Near-expiry coverage window",
                    suggested_actions=[
                        "Save invoice and serial details.",
                        "Run self-checks and log outputs for any claim.",
                    ],
                )
            )

    if not nudges:
        nudges.append(
            Nudge(
                id=generate_id("ndg"),
                warranty_id=risk.warranty_id,
                user_id=risk.user_id,
                title="All Good",
                message="No pressing actions. We will refresh advisories on schedule.",
                reason="Low risk and no expiry pressure",
                suggested_actions=[],
            )
        )

    return nudges
