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
def fresh_streamlit_cache(monkeypatch):
    """st.cache_data lives for the whole test process; isolate each test's rate card.
    Also hide any real API keys in the shell, so tests never call a live model."""
    st.cache_data.clear()
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_MODEL", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OOPS_PROOF_NO_SECRETS", "1")     # ignore a local .streamlit/secrets.toml too
    yield


def upload_file(at, path, name="bookings.xlsx"):
    """Put a workbook into the upload page's state, as a real upload does, then rerun."""
    from pathlib import Path
    from core.excel_loader import load_workbook
    data = Path(path).read_bytes()
    res = load_workbook(data)
    for k, v in dict(upload_source=name, upload_name=name, upload_bytes=data, fix_all_result=None,
                     upload_bookings=res.bookings, upload_file_issues=res.file_issues,
                     upload_notes=res.notes,
                     upload_pristine=[b.model_dump() for b in res.bookings]).items():
        at.session_state[k] = v
    return at.run()
