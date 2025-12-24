from typing import Optional, Callable

from . import acmeco, zenith

_SCRAPERS: dict[str, Callable[..., Optional[object]]] = {
    "acmeco": acmeco.fetch_terms,
    "zenith": zenith.fetch_terms,
}


def get_scraper(brand: Optional[str]):
    if not brand:
        return None
    key = brand.strip().lower().split()[0]
    return _SCRAPERS.get(key)
