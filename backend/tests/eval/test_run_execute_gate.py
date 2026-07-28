"""`eval.run` must confirm a pending plan before asserting expect.state.

The 2026-07-28 audit found the fix for "PASS only proved the model said
something" had been applied to `eval/run_isolated_e9.py` only: `eval.run` —
the entry point the docs tell you to use — read post-execution state without
ever executing anything, so all 200 generated cases carrying both
`expect.state` and `requires_confirmation` would have failed on state for a
reason that has nothing to do with the model. The mock regression cannot catch
it (state checks are skipped unless `--llm real`), hence these tests.
"""

from __future__ import annotations

import argparse
from typing import Any

import pytest

from eval.run import _execute_pending
from eval.schema import EvalCase

_PENDING = {"plan": {"status": "pending_approval", "workflow_id": "wf-1", "steps": []}}


def _case(**overrides: object) -> EvalCase:
    base: dict[str, object] = {"id": "t", "prompt": "p"}
    base.update(overrides)
    return EvalCase.model_validate(base)


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, Any] = {
        "mode": "api",
        "llm": "real",
        "token": "tok",
        "base_url": "http://backend/api/v1",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _stub_confirm(monkeypatch: pytest.MonkeyPatch, calls: list[tuple[str, str, str]]) -> None:
    def fake(base_url: str, token: str, workflow_id: str, **_: object) -> dict[str, Any]:
        calls.append((base_url, token, workflow_id))
        return {"status": "completed"}

    monkeypatch.setattr("eval.run.confirm_workflow_http", fake)


def test_confirms_pending_plan_when_case_expects_state(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, str]] = []
    _stub_confirm(monkeypatch, calls)
    case = _case(expect={"state": {"item_present": ["報告_正式版"]}})

    checks = _execute_pending(case, _args(), _PENDING)

    assert calls == [("http://backend/api/v1", "tok", "wf-1")]
    assert checks == []


def test_does_not_confirm_when_case_has_no_state_expectation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Confirming here would perform real writes on the developer's account for
    # an outcome nobody reads back.
    calls: list[tuple[str, str, str]] = []
    _stub_confirm(monkeypatch, calls)

    assert _execute_pending(_case(), _args(), _PENDING) == []
    assert calls == []


def test_does_not_confirm_when_the_case_simulates_a_user_who_never_approves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # safety_no_side_effect.yaml: auto_confirm=False + item_absent asserts the
    # plan did NOT take effect without approval. Confirming would invert the
    # exact safety property the case exists to prove.
    calls: list[tuple[str, str, str]] = []
    _stub_confirm(monkeypatch, calls)
    case = _case(auto_confirm=False, expect={"state": {"item_absent": ["Reports"]}})

    assert _execute_pending(case, _args(), _PENDING) == []
    assert calls == []


@pytest.mark.parametrize(
    "override",
    [{"mode": "browser"}, {"llm": "mock"}, {"token": ""}],
)
def test_does_not_confirm_when_state_is_unobservable(
    monkeypatch: pytest.MonkeyPatch, override: dict[str, object]
) -> None:
    calls: list[tuple[str, str, str]] = []
    _stub_confirm(monkeypatch, calls)
    case = _case(expect={"state": {"item_present": ["x"]}})

    assert _execute_pending(case, _args(**override), _PENDING) == []
    assert calls == []


@pytest.mark.parametrize(
    "response",
    [
        {"plan": None},
        {"skill_proposal": {"name": "md5"}},
        {"plan": {"status": "completed", "workflow_id": "wf-1"}},
        {"plan": {"status": "pending_approval"}},
    ],
)
def test_does_not_confirm_when_there_is_nothing_pending(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]
) -> None:
    calls: list[tuple[str, str, str]] = []
    _stub_confirm(monkeypatch, calls)
    case = _case(expect={"state": {"item_present": ["x"]}})

    assert _execute_pending(case, _args(), response) == []
    assert calls == []


def test_confirm_failure_is_recorded_as_a_check_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # One backend hiccup must cost that case its execution check, not abort the
    # whole batch.
    from eval.runner import EvalRunnerError

    def fake(*_: object, **__: object) -> dict[str, Any]:
        raise EvalRunnerError("confirm failed: 503 Service Unavailable")

    monkeypatch.setattr("eval.run.confirm_workflow_http", fake)
    case = _case(expect={"state": {"item_present": ["x"]}})

    checks = _execute_pending(case, _args(), _PENDING)

    assert len(checks) == 1
    assert checks[0].dimension == "execution"
    assert checks[0].ok is False
    assert "503" in (checks[0].detail or "")
