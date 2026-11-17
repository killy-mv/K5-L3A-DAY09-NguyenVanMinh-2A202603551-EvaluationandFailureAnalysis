"""M4 regression: ticket must never override the authoritative order delay."""
import pytest
from lab9 import variants
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


def test_c002_ticket_trust_regression():
    variants.register()
    bad = investigate("seeded_regression", "C-002", 11)["trial"]
    good = investigate("fixed", "C-002", 11)["trial"]

    assert any(e["kind"] == "model_override" and e["payload"]["delay_days"] == 5
               for e in bad["events"])
    assert not bad["lab8_pass"]
    assert bad["snapshot"]["refund_vnd"] == 20000

    assert not any(e["kind"] == "model_override" for e in good["events"])
    assert good["lab8_pass"]
    assert good["result"]["status"] == "denied"
    assert good["snapshot"]["refund_vnd"] == 0
