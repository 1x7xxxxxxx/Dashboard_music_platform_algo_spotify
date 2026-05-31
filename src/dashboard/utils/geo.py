"""ISO-2 → ISO-3 country-code helper for choropleth maps.

Type: Utility
Uses: pycountry
Persists in: nothing

Meta Ads returns ISO-3166 alpha-2 codes ('US', 'FR'); plotly px.choropleth needs
alpha-3 ('USA', 'FRA') with locationmode='ISO-3'. Thin cached wrapper over pycountry.
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=512)
def iso2_to_iso3(code: str | None) -> str | None:
    """Return the ISO-3 alpha-3 code for an alpha-2 code, or None if unknown."""
    if not code or len(code) != 2 or not code.isalpha():
        return None
    try:
        import pycountry
        match = pycountry.countries.get(alpha_2=code.upper())
        return match.alpha_3 if match else None
    except Exception:
        return None


@lru_cache(maxsize=512)
def iso2_to_name(code: str | None) -> str:
    """Return a human country name for an alpha-2 code, falling back to the code."""
    if not code:
        return "?"
    try:
        import pycountry
        match = pycountry.countries.get(alpha_2=code.upper())
        return match.name if match else code
    except Exception:
        return code
