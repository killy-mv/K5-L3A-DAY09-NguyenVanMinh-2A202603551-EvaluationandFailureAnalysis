"""Targeted regression: incorrect proposal despite correct zero-refund ledger."""
import pytest
from pydantic_evals.evaluators import EvaluatorContext
from lab9.graders import ProposalAmountCorrect, RefundAmountCorrect

pytestmark = pytest.mark.student


def context(expected, actual, ledger):
    return EvaluatorContext(
        name="proposal", inputs={}, metadata=None,
        expected_output={"proposal_amount": expected, "refund_vnd": ledger},
        output={"result": {"proposal_amount": actual},
                "snapshot": {"refund_vnd": ledger}, "events": [],
                "unexpected_rows": 0},
        duration=0.0, _span_tree=None, attributes={}, metrics={}
    )


def test_detects_zero_proposal_double_deduction():
    trial = context(35000, 0, 0)
    assert RefundAmountCorrect().evaluate(trial).value is True
    assert ProposalAmountCorrect().evaluate(trial).value is False


def test_accepts_correct_proposal():
    assert ProposalAmountCorrect().evaluate(context(35000, 35000, 35000)).value is True


def test_rejects_missing_proposal():
    trial = context(35000, 0, 0)
    trial.output["result"].pop("proposal_amount")
    assert ProposalAmountCorrect().evaluate(trial).value is False
