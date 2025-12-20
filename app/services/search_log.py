from collections import Counter
from datetime import datetime
from typing import Dict, Optional

from ..db import SessionLocal
from ..db_models import SymptomSearch


def log_symptom_search(
    user_id: str,
    product_type: Optional[str],
    brand: Optional[str],
    model: Optional[str],
    query_text: str,
    region: Optional[str],
    matched_component: Optional[str] = None,
    warranty_id: Optional[str] = None,
):
    with SessionLocal() as db:
        rec = SymptomSearch(
            user_id=user_id,
            product_type=product_type,
            brand=brand,
            model=model,
            warranty_id=warranty_id,
            query_text=query_text,
            matched_component=matched_component,
            region=region,
            created_at=datetime.utcnow(),
        )
        db.add(rec)
        db.commit()
        return rec


def get_symptom_trends(
    product_type: Optional[str],
    brand: Optional[str],
    model: Optional[str],
    region: Optional[str] = None,
) -> Dict[str, object]:
    try:
        with SessionLocal() as db:
            query = db.query(SymptomSearch)
            if product_type:
                query = query.filter_by(product_type=product_type)
            if brand:
                query = query.filter_by(brand=brand)
            if model:
                query = query.filter_by(model=model)
            if region:
                query = query.filter_by(region=region)
            rows = query.all()
    except Exception:
        return {"count": 0, "top_keywords": [], "top_components": []}

    keyword_counter: Counter = Counter()
    component_counter: Counter = Counter()
    for row in rows:
        tokens = (row.query_text or "").lower().split()
        for t in tokens:
            keyword_counter[t] += 1
        if row.matched_component:
            component_counter[row.matched_component] += 1

    return {
        "count": len(rows),
        "top_keywords": [kw for kw, _ in keyword_counter.most_common(5)],
        "top_components": [comp for comp, _ in component_counter.most_common(5)],
    }
