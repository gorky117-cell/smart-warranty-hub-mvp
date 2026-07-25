from app.models import TermsResult
from app.services import oem_product_knowledge


def test_build_product_knowledge_card_from_approved_oem_terms():
    result = TermsResult(
        duration_months=12,
        terms=[
            "Coverage of up to 1 year or 30,000 prints, whichever comes first.",
            "Warranty includes printhead coverage.",
        ],
        exclusions=["Physical damage is excluded."],
        claim_steps=["Warranty Check", "Service Center Locator"],
        source_url="https://www.epson.co.in/product",
        source_urls=["https://www.epson.co.in/product"],
    )

    card = oem_product_knowledge.build_product_knowledge_card(
        brand="Epson",
        model_code="L3250",
        product_name="Epson L3250 Printer",
        category="printer",
        region="IN",
        result=result,
        source_type="approved_oem_source",
    )

    assert card is not None
    assert card["doc_id"] == "oem_product_knowledge:epson:l3250:in"
    content = str(card["content"])
    assert "30,000 prints" in content
    assert "printhead" in content.lower()
    assert "Service Center Locator" in content
    assert "no customer invoice or behavior data" in content
    meta = card["metadata"]
    assert meta["public_oem_product_data"] is True
    assert meta["brand"] == "Epson"
    assert meta["model_code"] == "L3250"


def test_product_knowledge_rejects_unconfirmed_default_terms():
    result = TermsResult(
        duration_months=12,
        terms=["Standard coverage for 12 months from purchase date."],
        source_url="internal://default_rules",
    )

    card = oem_product_knowledge.build_product_knowledge_card(
        brand="Unknown",
        model_code="X1",
        product_name="Unknown Product",
        category="general",
        region="IN",
        result=result,
        source_type="default_rules",
    )

    assert card is None


def test_upsert_product_knowledge_card_uses_rag_document_without_customer_data(monkeypatch):
    calls = []

    def fake_add_event_documents(db, *, doc_type, doc_id, content, metadata):
        calls.append(
            {
                "doc_type": doc_type,
                "doc_id": doc_id,
                "content": content,
                "metadata": metadata,
            }
        )

    monkeypatch.setattr(oem_product_knowledge.rag, "add_event_documents", fake_add_event_documents)
    result = TermsResult(
        terms=["Warranty includes battery terms."],
        claim_steps=["Contact support."],
        source_url="test_data/oem/phone.html",
        source_urls=["test_data/oem/phone.html"],
    )

    card = oem_product_knowledge.upsert_product_knowledge_card(
        None,
        brand="Acme",
        model_code="P1",
        product_name="Acme Phone",
        category="smartphone",
        region="US",
        result=result,
        source_type="synthetic_approved",
    )

    assert card is not None
    assert calls
    assert calls[0]["doc_type"] == "oem_product_knowledge"
    assert "user_id" not in calls[0]["metadata"]
    assert "warranty_id" not in calls[0]["metadata"]
    assert "customer" not in calls[0]["content"].lower().replace("no customer", "")

