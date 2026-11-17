"""Regression: eval fingerprints are checkout-independent on Windows and Linux."""
import hashlib
from pathlib import Path

import pytest

from lab9.evalset import sha12

pytestmark = pytest.mark.student


def test_eval_sha_is_stable_between_lf_and_crlf(tmp_path):
    lf = tmp_path / "lf.jsonl"
    crlf = tmp_path / "crlf.jsonl"
    content = b'{"item_id":"E-001","value":"hello"}\n{"item_id":"E-002","value":"world"}\n'
    lf.write_bytes(content)
    crlf.write_bytes(content.replace(b"\n", b"\r\n"))
    assert sha12(lf) == sha12(crlf) == hashlib.sha256(content).hexdigest()[:12]


def test_eval_sha_detects_meaningful_content_change(tmp_path):
    file = tmp_path / "items.jsonl"
    file.write_bytes(b'{"value":1}\n')
    before = sha12(file)
    file.write_bytes(b'{"value":2}\r\n')
    assert sha12(file) != before


@pytest.mark.parametrize(
    "name,expected",
    [
        ("eval_set_v1.jsonl", "bd5fbe426b51"),
        ("eval_set_v2.jsonl", "fa73119313fa"),
    ],
)
def test_public_eval_hashes_are_checkout_independent(name, expected):
    assert sha12(Path(__file__).resolve().parents[1] / "data" / "eval" / name) == expected
