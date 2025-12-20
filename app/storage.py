import json
from typing import Dict, List
from uuid import uuid4
from datetime import datetime, date

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from .models import Artifact, BehaviourEvent, CanonicalWarranty, ReviewItem, ServiceTicket, TelemetryEvent
from .db import SessionLocal
from .db_models import ReviewDB, TelemetryEventDB, ArtifactDB, WarrantyDB, PolicyAssignmentDB


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


class MemoryStore:
    def __init__(self) -> None:
        self.artifacts: Dict[str, Artifact] = {}
        self.warranties: Dict[str, CanonicalWarranty] = {}
        self.behaviour_events: Dict[str, List[BehaviourEvent]] = {}
        self.tickets: Dict[str, ServiceTicket] = {}
        self.telemetry: Dict[str, List[TelemetryEvent]] = {}
        self.reviews: Dict[str, ReviewItem] = {}
        self.policy_assignments: Dict[str, str] = {}

    def add_artifact(self, artifact: Artifact) -> Artifact:
        self.artifacts[artifact.id] = artifact
        with SessionLocal() as db:
            db_art = ArtifactDB(
                id=artifact.id,
                type=artifact.type.value,
                content=artifact.content,
                source=artifact.source,
                received_at=artifact.received_at,
            )
            db.merge(db_art)
            db.commit()
        return artifact

    def add_warranty(self, warranty: CanonicalWarranty) -> CanonicalWarranty:
        self.warranties[warranty.id] = warranty
        with SessionLocal() as db:
            db_w = WarrantyDB(
                id=warranty.id,
                product_name=warranty.product_name,
                brand=warranty.brand,
                model_code=warranty.model_code,
                serial_no=warranty.serial_no,
                purchase_date=warranty.purchase_date,
                coverage_months=warranty.coverage_months,
                expiry_date=warranty.expiry_date,
                terms=warranty.terms,
                exclusions=warranty.exclusions,
                claim_steps=warranty.claim_steps,
                confidence=warranty.confidence,
                alternatives=warranty.alternatives,
                source_artifact_ids=warranty.source_artifact_ids,
                created_at=warranty.created_at,
            )
            db.merge(db_w)
            db.commit()
        return warranty

    def add_behaviour_event(self, event: BehaviourEvent) -> BehaviourEvent:
        key = f"{event.user_id}:{event.warranty_id}"
        self.behaviour_events.setdefault(key, []).append(event)
        return event

    def get_behaviour_events(self, user_id: str, warranty_id: str) -> List[BehaviourEvent]:
        key = f"{user_id}:{warranty_id}"
        return self.behaviour_events.get(key, [])

    def add_ticket(self, ticket: ServiceTicket) -> ServiceTicket:
        self.tickets[ticket.id] = ticket
        return ticket

    def list_tickets(self, warranty_id: str) -> List[ServiceTicket]:
        return [t for t in self.tickets.values() if t.warranty_id == warranty_id]

    def add_telemetry(self, event: TelemetryEvent) -> TelemetryEvent:
        key = f"{event.user_id}:{event.warranty_id}"
        self.telemetry.setdefault(key, []).append(event)
        with SessionLocal() as db:
            db_ev = TelemetryEventDB(
                id=event.id,
                user_id=event.user_id,
                warranty_id=event.warranty_id,
                model_code=event.model_code,
                region=event.region,
                timezone=event.timezone,
                event_type=event.event_type,
                payload=event.payload,
                timestamp=event.timestamp,
            )
            db.merge(db_ev)
            db.commit()
        return event

    def get_telemetry(self, user_id: str, warranty_id: str) -> List[TelemetryEvent]:
        key = f"{user_id}:{warranty_id}"
        events = self.telemetry.get(key, []).copy()
        with SessionLocal() as db:
            stmt = select(TelemetryEventDB).where(
                TelemetryEventDB.user_id == user_id, TelemetryEventDB.warranty_id == warranty_id
            )
            for ev in db.execute(stmt).scalars().all():
                events.append(
                    TelemetryEvent(
                        id=ev.id,
                        warranty_id=ev.warranty_id,
                        user_id=ev.user_id,
                        model_code=ev.model_code,
                        region=ev.region,
                        timezone=ev.timezone,
                        event_type=ev.event_type,
                        payload=ev.payload or {},
                        timestamp=ev.timestamp,
                    )
                )
        return events

    def add_review(self, item: ReviewItem) -> ReviewItem:
        self.reviews[item.id] = item
        return item

    def update_review(self, review_id: str, status: str, reason: str | None = None) -> ReviewItem:
        if review_id not in self.reviews:
            raise KeyError("review not found")
        item = self.reviews[review_id]
        item.status = status
        item.reason = reason
        item.resolved_at = datetime.utcnow()
        self.reviews[review_id] = item
        return item

    def list_reviews(self, status: str | None = None) -> List[ReviewItem]:
        if status is None:
            return list(self.reviews.values())
        return [r for r in self.reviews.values() if r.status == status]

    def get_policy_variant(self, experiment: str, user_id: str, warranty_id: str) -> str | None:
        key = f"{experiment}:{user_id}:{warranty_id}"
        # check in-memory
        if key in self.policy_assignments:
            return self.policy_assignments[key]
        with SessionLocal() as db:
            stmt = select(PolicyAssignmentDB).where(
                PolicyAssignmentDB.experiment == experiment,
                PolicyAssignmentDB.user_id == user_id,
                PolicyAssignmentDB.warranty_id == warranty_id,
            )
            res = db.execute(stmt).scalars().first()
            if res:
                self.policy_assignments[key] = res.variant
                return res.variant
        return None

    def set_policy_variant(self, experiment: str, user_id: str, warranty_id: str, variant: str) -> str:
        key = f"{experiment}:{user_id}:{warranty_id}"
        self.policy_assignments[key] = variant
        with SessionLocal() as db:
            db.merge(
                PolicyAssignmentDB(
                    experiment=experiment, user_id=user_id, warranty_id=warranty_id, variant=variant
                )
            )
            db.commit()
        return variant

    @staticmethod
    def _parse_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return None
        return None

    @staticmethod
    def _as_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except ValueError:
                return []
        return []

    @staticmethod
    def _as_dict(value):
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except ValueError:
                return {}
        return {}

    def _row_to_warranty(self, row_dict: dict) -> CanonicalWarranty:
        return CanonicalWarranty(
            id=row_dict["id"],
            product_name=row_dict.get("product_name"),
            brand=row_dict.get("brand"),
            model_code=row_dict.get("model_code"),
            serial_no=row_dict.get("serial_no"),
            purchase_date=self._parse_date(row_dict.get("purchase_date")),
            coverage_months=row_dict.get("coverage_months"),
            expiry_date=self._parse_date(row_dict.get("expiry_date")),
            terms=self._as_list(row_dict.get("terms")),
            exclusions=self._as_list(row_dict.get("exclusions")),
            claim_steps=self._as_list(row_dict.get("claim_steps")),
            confidence=self._as_dict(row_dict.get("confidence")),
            alternatives=self._as_dict(row_dict.get("alternatives")),
            source_artifact_ids=self._as_list(row_dict.get("source_artifact_ids")),
            created_at=row_dict.get("created_at") or datetime.utcnow(),
        )

    def _load_warranty_row(self, db, warranty_id: str):
        """
        Load a warranty row, tolerating older SQLite files that are missing newer columns.
        """
        try:
            row = db.get(WarrantyDB, warranty_id)
            if row:
                return {
                    "id": row.id,
                    "product_name": row.product_name,
                    "brand": row.brand,
                    "model_code": row.model_code,
                    "serial_no": row.serial_no,
                    "purchase_date": row.purchase_date,
                    "coverage_months": row.coverage_months,
                    "expiry_date": row.expiry_date,
                    "terms": row.terms,
                    "exclusions": row.exclusions,
                    "claim_steps": row.claim_steps,
                    "confidence": row.confidence,
                    "alternatives": row.alternatives,
                    "source_artifact_ids": row.source_artifact_ids,
                    "created_at": row.created_at,
                }
        except OperationalError:
            columns = [r[1] for r in db.execute(text("PRAGMA table_info(warranties)")).all()]
            base_columns = [
                "id",
                "product_name",
                "brand",
                "model_code",
                "serial_no",
                "purchase_date",
                "coverage_months",
                "expiry_date",
                "terms",
                "exclusions",
                "claim_steps",
                "confidence",
                "alternatives",
                "source_artifact_ids",
                "created_at",
            ]
            available = [c for c in base_columns if c in columns]
            if not available:
                return None
            stmt = text(f"SELECT {', '.join(available)} FROM warranties WHERE id = :id")
            res = db.execute(stmt, {"id": warranty_id}).first()
            if not res:
                return None
            return dict(zip(available, res))
        return None

    def get_warranty_db(self, warranty_id: str) -> CanonicalWarranty | None:
        if warranty_id in self.warranties:
            return self.warranties[warranty_id]
        with SessionLocal() as db:
            data = self._load_warranty_row(db, warranty_id)
            if not data:
                return None
            cw = self._row_to_warranty(data)
            self.warranties[warranty_id] = cw
            return cw


store = MemoryStore()
