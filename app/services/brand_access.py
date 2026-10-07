"""Brand accounts see only their own brand (owner review of PR #3, item 3).

An admin links each brand/OEM/TPA account to its brand(s) (table oem_account_brands). Every OEM endpoint that
returns counts calls scoped_brand():
- admin: any brand, or all brands when none is asked for;
- brand account asking for its own brand (any letter case): allowed;
- brand account asking for another brand: 403;
- brand account asking for no brand: its own brand (one linked brand), or 422 when it has several;
- brand account not linked to any brand yet: 403.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db_models import OemAccountBrandDB

NOT_LINKED = "This account is not linked to a brand yet. Please ask Smart Warranty Hub to link it."
OTHER_BRAND = "Brand accounts can only see counts for their own brand."


def linked_brands(db: Session, username: str) -> List[str]:
    return [row.brand for row in db.query(OemAccountBrandDB).filter_by(username=username).order_by(OemAccountBrandDB.brand)]


def set_linked_brands(db: Session, username: str, brands: List[str], *, admin: str) -> List[str]:
    clean = sorted({" ".join(str(b).split()) for b in brands if str(b).strip()})
    db.query(OemAccountBrandDB).filter_by(username=username).delete()
    for brand in clean:
        db.add(OemAccountBrandDB(username=username, brand=brand, created_by=admin, created_at=datetime.utcnow()))
    db.commit()
    return clean


def scoped_brand(db: Session, current, requested: Optional[str]) -> Optional[str]:
    """The brand this request may see counts for (None = all brands, admins only)."""
    if getattr(current, "role", None) == "admin":
        return requested or None
    allowed = linked_brands(db, current.username)
    if not allowed:
        raise HTTPException(status_code=403, detail=NOT_LINKED)
    if not requested:
        if len(allowed) == 1:
            return allowed[0]
        raise HTTPException(status_code=422, detail=f"Choose one of your brands: {', '.join(allowed)}.")
    for brand in allowed:
        if brand.lower() == str(requested).strip().lower():
            return brand
    raise HTTPException(status_code=403, detail=OTHER_BRAND)


def allowed_brand_keys(db: Session, current) -> Optional[set]:
    """Lower-case brands this account may see in all-brand lists; None for admins (everything)."""
    if getattr(current, "role", None) == "admin":
        return None
    allowed = linked_brands(db, current.username)
    if not allowed:
        raise HTTPException(status_code=403, detail=NOT_LINKED)
    return {b.lower() for b in allowed}


# Shown at every question whose answers could count in brand totals (owner's wording, PR #3 review item 4).
ANONYMOUS_TOTALS_CONSENT = (
    "Allow SWH to share anonymous totals (never your name or details) with the brand, only for groups of 10 or "
    "more people. You can change this anytime."
)
MIN_GROUP = 10


def totals_allowed(db: Session, user_id: str) -> bool:
    """Opt-in only: no answer yet means not allowed."""
    from ..db_models import AnonymousTotalsConsentDB

    row = db.get(AnonymousTotalsConsentDB, user_id)
    return bool(row and row.allow)


def set_totals_allowed(db: Session, user_id: str, allow: bool) -> None:
    from ..db_models import AnonymousTotalsConsentDB

    row = db.get(AnonymousTotalsConsentDB, user_id)
    if row is None:
        db.add(AnonymousTotalsConsentDB(user_id=user_id, allow=allow, updated_at=datetime.utcnow()))
    else:
        row.allow, row.updated_at = allow, datetime.utcnow()
    db.commit()
