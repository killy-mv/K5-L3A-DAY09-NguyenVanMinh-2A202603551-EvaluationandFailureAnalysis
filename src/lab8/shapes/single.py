"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8
# Internal loop outcome meaning "the quote tool ran; code takes over". Not a RunResult status.
_QUOTED = "quoted"


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    except InjectedCrash:
        raise  # T12: the crash must surface; the trace was flushed before re-raise.
    except Exception as exc:  # contract: run_claim never raises; fail closed with a trace.
        return _failed_on_exception(conn, claim_id, seed, exc)
    finally:
        conn.close()


def _make_decide(budget: Budget, seed: int, memory: dict[str, Any]):
    """Model policy for the ReAct loop. It may only pick read tools.

    Every call is charged as one model call. Decisions come from tool results
    (order row, quote), never from numbers written in the ticket.
    Side effect: each tool result is stored in `memory[tool_name]`, which the
    caller reads after the loop to take the quote from the tool, not the model.
    """

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        claim = seen["claim"]
        last_tool = seen.get("last_tool")
        prompt = claim["ticket"] if last_tool is None else f"observed:{last_tool}"
        complete(budget, seed=seed, purpose="react", prompt=prompt)

        if last_tool is not None:
            memory[last_tool] = seen["last_result"]

        if not claim.get("order_id"):
            return {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}

        order_view = memory.get("lookup_order")
        if order_view is None:
            return {
                "tool": "lookup_order",
                "args": {"order_id": claim["order_id"], "principal_id": claim["principal_id"]},
            }
        if not order_view["visible"]:
            return {"final": {"status": "escalated", "error_reason": order_view["reason"]}}

        if "compute_compensation" not in memory:
            return {"tool": "compute_compensation", "args": {"order": order_view["order"]}}
        return {"final": {"status": _QUOTED}}

    return decide


def _failed_on_exception(conn: sqlite3.Connection, claim_id: str, seed: int, exc: Exception) -> RunResult:
    reason = f"exception:{type(exc).__name__}"  # type name only: the message may carry row data
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    trace.add("error", {"reason": reason})
    try:
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=Budget(),
            trace=trace,
            error_reason=reason,
        )
    except Exception:  # store unreadable: report no effects rather than raise
        return RunResult(
            run_id=trace.run_id, claim_id=claim_id, shape=SHAPE, seed=seed, status="failed",
            proposal_amount=0, refund_effects=[], committed_audit_count=0, model_calls=0,
            tool_calls=0, input_tokens=0, output_tokens=0, cost_estimate=0.0,
            trace_path=trace.write(), error_reason=reason,
        )


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        complete(budget, seed=seed, purpose="draft", prompt=status)
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        return done("failed", 0, "unknown_claim")

    memory: dict[str, Any] = {}
    loop = run_react(
        conn,
        budget,
        observation={"claim": claim},
        decide=_make_decide(budget, seed, memory),
        max_steps=MAX_STEPS,
    )
    # Trace only the tool names and outcome; never the ticket or raw rows.
    trace.add("react", {"stopped": loop["stopped"], "tools": list(memory), "final": loop["final"]})

    final = loop["final"]
    if final["status"] != _QUOTED:
        return done(final["status"], 0, final.get("error_reason"))

    # Code, not the model, owns the money: amount comes from the deterministic tool result.
    quote = memory["compute_compensation"]
    proposal = int(quote["amount_vnd"])
    trace.add("quote", quote)
    if proposal <= 0:
        return done("denied", 0, quote["reason"])

    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("issue_refund", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})

    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)
