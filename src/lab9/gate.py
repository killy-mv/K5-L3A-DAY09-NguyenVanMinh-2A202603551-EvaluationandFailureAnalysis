"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    def finite(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

    def inspect(report, label):
        manifest = report.get('manifest') or {}
        rows = report.get('rows') or []
        metrics = report.get('metrics') or {}
        count = manifest.get('items')
        seeds = manifest.get('seeds')
        if not isinstance(count, int) or count < 1 or not isinstance(seeds, list) or not seeds:
            problems.append(f'{label}: invalid manifest')
            return set()
        if any(not isinstance(x, int) or isinstance(x, bool) for x in seeds) or len(set(seeds)) != len(seeds):
            problems.append(f'{label}: invalid or duplicated seeds')
            return set()
        if len(rows) != count * len(seeds):
            problems.append(f'{label}: missing or extra rows')
        if report.get('evaluator_failures'):
            problems.append(f'{label}: evaluator failures')
        for mid, value in metrics.items():
            if value is not None and not finite(value):
                problems.append(f'{label}: non-finite metric {mid}')
        for m in spec['metrics']:
            if not finite(metrics.get(m['id'])):
                problems.append(f'{label}: missing metric {m["id"]}')
        summary = {'pass_5', 'pass_hat_5', 'cost_per_success'}
        scored = [m['id'] for m in spec['metrics'] if m['id'] not in summary]
        pairs = []
        tag_by_item = {}
        for row in rows:
            item, seed = row.get('item_id'), row.get('seed')
            if not isinstance(item, str) or not isinstance(seed, int):
                problems.append(f'{label}: invalid row identity')
                continue
            pairs.append((item, seed))
            tags = row.get('slices', [])
            if not isinstance(tags, list) or any(not isinstance(x, str) for x in tags):
                problems.append(f'{label}: invalid slice tags')
                tags = []
            if item in tag_by_item and tag_by_item[item] != frozenset(tags):
                problems.append(f'{label}: inconsistent slices for {item}')
            tag_by_item[item] = frozenset(tags)
            for mid in scored:
                if type(row.get(mid)) is not bool:
                    problems.append(f'{label}: missing/invalid grader {mid} at {item}@{seed}')
        item_ids = {item for item, _ in pairs}
        expected = {(item, seed) for item in item_ids for seed in seeds}
        if len(item_ids) != count or set(pairs) != expected or len(pairs) != len(set(pairs)):
            problems.append(f'{label}: missing/duplicated or cherry-picked item/seed rows')
        for mid in scored:
            if not rows or any(type(row.get(mid)) is not bool for row in rows):
                continue
            values = [row[mid] for row in rows]
            computed = sum(values) if mid in ('approval_bypass', 'secret_leak') else round(sum(values)/len(values), 4)
            if finite(metrics.get(mid)) and abs(metrics[mid] - computed) > 0.00011:
                problems.append(f'{label}: metric {mid} differs from raw rows')
        if finite(metrics.get('pass_hat_5')):
            grouped = {}
            for row in rows:
                grouped.setdefault(row['item_id'], []).append(row.get('pass_rate'))
            if grouped and all(len(vals)==5 and all(type(v) is bool for v in vals) for vals in grouped.values()):
                observed = round(sum(all(vals) for vals in grouped.values())/len(grouped),4)
                if abs(metrics['pass_hat_5'] - observed) > 0.00011:
                    problems.append(f'{label}: pass_hat_5 differs from raw rows')
        return set(pairs), tag_by_item

    pr_result = inspect(pr, 'PR')
    base_result = inspect(base, 'baseline')
    if pr_result and base_result:
        if pr_result[0] != base_result[0]:
            problems.append('item/seed set differs from baseline')
        if pr_result[1] != base_result[1]:
            problems.append('slice tags differ from baseline')
    if pr.get('manifest',{}).get('seeds') != base.get('manifest',{}).get('seeds'):
        problems.append('PR seeds differ from baseline')
    if spec.get('seeds') and pr.get('manifest',{}).get('seeds') != spec['seeds']:
        problems.append('seeds differ from spec')

    if base_spec is not None and spec.get('eval_set_version') == base_spec.get('eval_set_version'):
        for field, key in [('metrics','id'), ('slices','name')]:
            current = {x[key]:x for x in spec.get(field, [])}
            previous = {x[key]:x for x in base_spec.get(field, [])}
            if len(current) != len(spec.get(field, [])):
                problems.append(f'duplicate {field} spec entries')
            for name, old_entry in previous.items():
                new_entry = current.get(name)
                if new_entry is None:
                    problems.append(f'removed {field} {name}')
                    continue
                if old_entry.get('blocking') and not new_entry.get('blocking'):
                    problems.append(f'disabled blocking for {name}')
                if field == 'metrics':
                    if old_entry.get('kind')=='safety' and new_entry.get('kind')!='safety':
                        problems.append(f'demoted safety metric {name}')
                    if old_entry.get('grader') != new_entry.get('grader'):
                        problems.append(f'changed grader of {name}')
                elif new_entry.get('metric') != old_entry.get('metric'):
                    problems.append(f'changed slice metric {name}')
                old_th = old_entry.get('threshold', {}) if field=='metrics' else old_entry
                new_th = new_entry.get('threshold', {}) if field=='metrics' else new_entry
                for param in ('min','max','max_increase'):
                    if param not in old_th:
                        continue
                    value = new_th.get(param)
                    if not finite(value):
                        problems.append(f'removed/invalid {param} threshold of {name}')
                    elif (param=='min' and value < old_th[param]) or (param!='min' and value > old_th[param]):
                        problems.append(f'loosened {param} threshold of {name}')
                if old_th.get('no_significant_drop') and not new_th.get('no_significant_drop'):
                    problems.append(f'removed no_significant_drop of {name}')
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for entry in spec.get("slices") or []:
        name = entry["name"]
        mid = entry["metric"]
        key = f"slice:{name}/{mid}"
        current = per_item(pr, mid, slice_name=name)
        baseline = per_item(base, mid, slice_name=name)
        keys = sorted(set(current) & set(baseline))
        verdict = "ok"
        details = ""
        if not keys or set(current) != set(baseline):
            verdict = "missing"
        else:
            value = sum(current[k] for k in keys) / len(keys)
            details = f"mean={value:.4f}, items={len(keys)}"
            if "min" in entry and value < entry["min"]:
                verdict = "fail"
            if "max" in entry and value > entry["max"]:
                verdict = "fail"
            if entry.get("no_significant_drop"):
                difference, lo, hi = stats.paired_bootstrap(
                    [current[k] for k in keys],
                    [baseline[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )
                details += f", Δ {difference:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and entry.get("blocking", False):
            blocked.append(key)
        label = "ok" if verdict == "ok" else (
            "BLOCK" if entry.get("blocking") else "warn")
        lines.append(f"  {key:<38} {details:<62} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
