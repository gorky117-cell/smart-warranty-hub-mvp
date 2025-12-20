from typing import List, Optional

from ..models import ServiceTicket
from ..storage import generate_id, store


SYMPTOM_TO_PARTS = {
    "no_cooling": ["capacitor", "blower_motor"],
    "noise": ["suspension_kit", "drum_stabiliser"],
    "power_failure": ["power_board"],
}


def create_ticket(
    user_id: str,
    warranty_id: str,
    symptom: str,
    evidence: Optional[List[str]] = None,
) -> ServiceTicket:
    evidence = evidence or []
    recommended_parts = SYMPTOM_TO_PARTS.get(symptom, [])
    ticket = ServiceTicket(
        id=generate_id("tkt"),
        warranty_id=warranty_id,
        user_id=user_id,
        symptom=symptom,
        evidence=evidence,
        recommended_parts=recommended_parts,
        status="draft",
    )
    return store.add_ticket(ticket)
