"""M7 integrity adversarial unit tests, without changing any generated report."""
import copy
import json
from pathlib import Path

import pytest

from lab9.gate import integrity_check
from lab9.eval import load_spec

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def context():
    base=json.loads(Path("reports/baseline_v2.json").read_text(encoding="utf-8"))
    pr=json.loads(Path("reports/eval_fixed_v2.json").read_text(encoding="utf-8"))
    spec=load_spec(Path("config/metric_spec_v2.yaml"))
    assert not integrity_check(pr,base,spec,spec)
    return pr,base,spec


@pytest.mark.parametrize("tamper", [
    "nan", "inf", "deleted_row", "duplicated_row", "changed_seed",
    "grader_crash", "missing_score", "fake_aggregate", "relabeled_slice",
    "altered_reliability", "invalid_manifest",
])
def test_rejects_corrupted_report(context, tamper):
    pr,base,spec=(copy.deepcopy(x) for x in context)
    if tamper=="nan": pr["metrics"]["pass_rate"]=float("nan")
    elif tamper=="inf": pr["metrics"]["cost_per_success"]=float("inf")
    elif tamper=="deleted_row": pr["rows"].pop()
    elif tamper=="duplicated_row": pr["rows"][0]=copy.deepcopy(pr["rows"][1])
    elif tamper=="changed_seed": pr["rows"][0]["seed"]=999
    elif tamper=="grader_crash": pr["evaluator_failures"].append("crash")
    elif tamper=="missing_score": pr["rows"][0]["refund_amount_correct"]=None
    elif tamper=="fake_aggregate": pr["metrics"]["pass_rate"]=0.9
    elif tamper=="relabeled_slice": pr["rows"][0]["slices"]=[]
    elif tamper=="altered_reliability": pr["metrics"]["pass_hat_5"]=0.8
    elif tamper=="invalid_manifest": pr["manifest"]["items"]=27
    assert integrity_check(pr,base,spec,spec),tamper


@pytest.mark.parametrize("tamper", [
    "loosen_min", "loosen_max", "drop_metric", "disable_block",
    "remove_ci", "drop_slice", "loosen_slice", "disable_slice",
    "remove_slice_ci", "swap_slice_metric",
])
def test_spec_ratchet(context, tamper):
    pr,base,spec=(copy.deepcopy(x) for x in context)
    if tamper=="loosen_min": spec["metrics"][4]["threshold"]["min"]=0.1
    elif tamper=="loosen_max": spec["metrics"][0]["threshold"]["max"]=1
    elif tamper=="drop_metric": spec["metrics"].pop(0)
    elif tamper=="disable_block": spec["metrics"][0]["blocking"]=False
    elif tamper=="remove_ci": spec["metrics"][4]["threshold"].pop("no_significant_drop")
    elif tamper=="drop_slice": spec["slices"].pop()
    elif tamper=="loosen_slice": spec["slices"][0]["min"]=0.4
    elif tamper=="disable_slice": spec["slices"][0]["blocking"]=False
    elif tamper=="remove_slice_ci": spec["slices"][0]["no_significant_drop"]=False
    elif tamper=="swap_slice_metric": spec["slices"][0]["metric"]="refund_amount_correct"
    assert integrity_check(pr,base,spec,context[2]),tamper


def test_baseline_unmodified_passes_integrity(context):
    pr,base,spec=context
    assert integrity_check(pr,base,spec,spec)==[]
