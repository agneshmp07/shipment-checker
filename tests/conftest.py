import pytest
import streamlit as st

from core.carriers import load_carriers
from core.models import CarrierOption

UK = "United Kingdom"


def _c(name, dest, price, days, on_time, max_kg):
    return CarrierOption(carrier=name, service="Test service", origin_country=UK, destination_country=dest,
                         price_per_pallet=price, transit_days=days, on_time_rate=on_time,
                         max_weight_per_pallet_kg=max_kg)


# TEST-ONLY stand-in for the real rate card, used until data/carriers.json exists.
STANDIN_CARRIERS = [
    _c(n, d, p, t, o, m)
    for d in ("Germany", "France", "Netherlands")
    for n, p, t, o, m in (("Test A", 180, 5, 92, 500), ("Test B", 250, 3, 96, 400), ("Test C", 150, 7, 85, 600))
]


@pytest.fixture
def carriers():
    """Real rate card if present, else the test stand-in."""
    return load_carriers() or STANDIN_CARRIERS


@pytest.fixture(autouse=True)
def fresh_streamlit_cache():
    """st.cache_data lives for the whole test process; isolate each test's rate card."""
    st.cache_data.clear()
    yield
