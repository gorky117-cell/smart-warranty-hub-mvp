"""Purchase date from many invoice phrasings and formats (batch 3 item 1, GLOBAL RULE: not one invoice)."""
from pathlib import Path

import pytest

from app.services.ingestion import extract_product_fields, find_purchase_date, parse_date_from_text

FIXTURE = Path(__file__).parent / "fixtures" / "invoices" / "amazon_2017_voltas_window_ac.txt"


@pytest.mark.parametrize("raw", ["Apr 22, 2017", "22 Apr 2017", "22/04/2017", "2017-04-22", "22-04-2017", "22.04.2017",
                                 "April 22 2017", "22nd April, 2017", "22-Apr-17", "Apr-22-2017", "2017/04/22"])
def test_date_formats(raw):
    assert parse_date_from_text(f"something {raw} more") == "2017-04-22"


@pytest.mark.parametrize("text,expected,conf", [
    ("Invoice for DMVVzZMtnN Apr 22, 2017\nTotal Rs. 100", "2017-04-22", 0.8),
    ("Packing slip for 402-1234567-1234567 22/04/2017", "2017-04-22", 0.8),
    ("Tax Invoice for ABC123 22 Apr 2017", "2017-04-22", 0.8),
    ("Invoice Date: 22.04.2017\nDue Date: 30.04.2017", "2017-04-22", 0.8),
    ("Due Date: 30.04.2017\nInvoice Date: 22.04.2017", "2017-04-22", 0.8),
    ("Order placed 22 April 2017", "2017-04-22", 0.8),
    ("Ordered on Apr 22, 2017", "2017-04-22", 0.8),
    ("Order Date : 2017-04-22", "2017-04-22", 0.8),
    ("Bill Date 22/04/17", "2017-04-22", 0.8),
    ("Dated 22-Apr-2017", "2017-04-22", 0.8),
    ("Date: 22/04/2017", "2017-04-22", 0.8),
    ("Warranty valid till 22/04/2019\nDate: 22/04/2017", "2017-04-22", 0.8),
    ("Thanks for shopping 22/04/2017", "2017-04-22", 0.5),
    ("Amazon.in invoice 2017\n0422-10:15", "2017-04-22", 0.4),   # footer stamp, the invoice's only year
])
def test_where_the_date_is_found(text, expected, conf):
    assert find_purchase_date(text) == (expected, conf)


def test_footer_stamp_needs_exactly_one_year():
    assert find_purchase_date("printed 0422-10:15")[0] is None
    assert find_purchase_date("2016 and 2017\n0422-10:15")[0] is None
    assert find_purchase_date("2017\n1399-10:15")[0] is None  # not a month/day


def test_implausible_years_are_ignored():
    assert parse_date_from_text("Invoice 12/12/1850") is None
    assert parse_date_from_text("ref 01/01/2999") is None


def test_amazon_fixture_date():
    fields, confidence, _alt = extract_product_fields(FIXTURE.read_text(encoding="utf-8"))
    assert fields["purchase_date"] == "2017-04-22" and confidence["purchase_date"] == 0.8
