"""Property-based tests for the eval harness itself (part of E1's self-tests).

These do NOT evaluate the assistant — they test that the harness's verifier and
scoring behave correctly under randomised cases and (possibly malformed) agent
responses. The harness must never crash on weird output, and its verdict must
faithfully reflect whether the declared expectations hold.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from eval.schema import EvalCase, Expect, Scoring, WorkflowExpect
from eval.scoring import score_case
from eval.verifier import CheckResult, verify

SKILLS = ["storage_quota", "list_items", "search", "create_folder", "trash_item"]
STATUSES = ["auto_executed", "pending_approval", "weird", ""]


# --- Strategies -------------------------------------------------------------

# Responses are dicts (what run_case returns) but with intentionally messy inner
# shapes — plan may be missing, None, a non-dict, or have odd steps.
wild_responses = st.fixed_dictionaries(
    {
        "message": st.text(max_size=10),
        "plan": st.one_of(
            st.none(),
            st.text(max_size=4),
            st.fixed_dictionaries(
                {
                    "status": st.sampled_from([*STATUSES, None]),
                    "steps": st.lists(
                        st.one_of(
                            st.fixed_dictionaries({"skill": st.sampled_from(SKILLS)}),
                            st.text(max_size=3),
                        ),
                        max_size=4,
                    ),
                }
            ),
        ),
        "results": st.lists(st.dictionaries(st.text(max_size=3), st.integers()), max_size=3),
        "skill_proposal": st.one_of(
            st.none(), st.fixed_dictionaries({"name": st.sampled_from(SKILLS)})
        ),
    }
)

case_expectations = st.builds(
    lambda inc, conf, gen: EvalCase(
        id="t",
        prompt="p",
        expect=Expect(
            workflow=WorkflowExpect(
                steps_include=inc, requires_confirmation=conf, skill_generated=gen
            )
        ),
    ),
    st.lists(st.sampled_from(SKILLS), max_size=2),
    st.one_of(st.none(), st.booleans()),
    st.one_of(st.none(), st.sampled_from(SKILLS)),
)

check_values = st.builds(
    lambda dim, ok: CheckResult(dimension=dim, name="c", ok=ok, detail=""),
    st.sampled_from(["correctness", "safety", "other"]),
    st.booleans(),
)


# --- Properties -------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(case_expectations, wild_responses)
def test_verify_is_total(case: EvalCase, response: dict[str, Any]) -> None:
    checks = verify(case, response)  # must never raise on malformed responses
    assert isinstance(checks, list)
    assert checks  # always at least one check
    assert all(isinstance(c.ok, bool) for c in checks)


@settings(max_examples=300, deadline=None)
@given(case_expectations, st.lists(check_values, max_size=6))
def test_score_is_bounded_and_pass_matches_threshold(
    case: EvalCase, checks: list[CheckResult]
) -> None:
    score = score_case(case, checks)
    assert 0.0 <= score.score <= 1.0
    assert score.passed == (score.score >= case.scoring.pass_threshold)


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=1, max_value=5))
def test_all_pass_is_one_all_fail_is_zero(count: int) -> None:
    case = EvalCase(id="t", prompt="p", scoring=Scoring(weights={"correctness": 1.0}))
    all_ok = [CheckResult("correctness", "c", True, "") for _ in range(count)]
    all_fail = [CheckResult("correctness", "c", False, "") for _ in range(count)]
    assert score_case(case, all_ok).score == 1.0
    assert score_case(case, all_fail).score == 0.0


@settings(max_examples=300, deadline=None)
@given(
    st.lists(st.sampled_from(SKILLS), max_size=4),
    st.sampled_from(SKILLS),
    st.sampled_from(STATUSES),
    st.one_of(st.none(), st.booleans()),
)
def test_verify_reflects_ground_truth(
    plan_skills: list[str],
    expected_skill: str,
    status: str,
    requires_confirmation: bool | None,
) -> None:
    response = {
        "message": "m",
        "plan": {"status": status, "steps": [{"skill": s} for s in plan_skills]},
    }
    case = EvalCase(
        id="t",
        prompt="p",
        expect=Expect(
            workflow=WorkflowExpect(
                steps_include=[expected_skill],
                requires_confirmation=requires_confirmation,
            )
        ),
    )
    checks = verify(case, response)

    include_check = next(c for c in checks if c.name.startswith("plan includes"))
    assert include_check.ok == (expected_skill in plan_skills)

    if requires_confirmation is not None:
        status_check = next(c for c in checks if c.name.startswith("plan status"))
        expected_status = "pending_approval" if requires_confirmation else "auto_executed"
        assert status_check.ok == (status == expected_status)


@settings(max_examples=300, deadline=None)
@given(
    st.lists(st.sampled_from(SKILLS), min_size=1, max_size=4),
    st.sampled_from(SKILLS),
    st.sampled_from(STATUSES),
    st.booleans(),
)
def test_passes_iff_every_expectation_met(
    plan_skills: list[str],
    expected_skill: str,
    status: str,
    requires_confirmation: bool,
) -> None:
    # A correctness-only case with a strict 1.0 threshold: it must pass exactly
    # when both the skill-inclusion and the confirmation expectation hold.
    response = {
        "message": "m",
        "plan": {"status": status, "steps": [{"skill": s} for s in plan_skills]},
    }
    case = EvalCase(
        id="t",
        prompt="p",
        expect=Expect(
            workflow=WorkflowExpect(
                steps_include=[expected_skill],
                requires_confirmation=requires_confirmation,
            )
        ),
        scoring=Scoring(weights={"correctness": 1.0}, pass_threshold=1.0),
    )
    expected_status = "pending_approval" if requires_confirmation else "auto_executed"
    ground_truth = (expected_skill in plan_skills) and (status == expected_status)

    assert score_case(case, verify(case, response)).passed == ground_truth
