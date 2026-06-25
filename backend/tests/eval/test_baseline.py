from __future__ import annotations

from pathlib import Path

from eval.baseline import (
    compare_to_baseline,
    comparison_to_markdown,
    has_regression,
    load_baseline,
    save_baseline,
)
from eval.scoring import CaseScore


def _score(case_id: str, score: float, passed: bool = True) -> CaseScore:
    return CaseScore(case_id=case_id, score=score, passed=passed)


def test_save_and_load_baseline_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    save_baseline(path, [_score("a", 1.0), _score("b", 0.5)])
    loaded = load_baseline(path)
    assert loaded == {"a": 1.0, "b": 0.5}


def test_compare_flags_regression_and_improvement() -> None:
    baseline = {"a": 1.0, "b": 0.5}
    scores = [_score("a", 0.4), _score("b", 0.9)]
    comparisons = {c.case_id: c for c in compare_to_baseline(scores, baseline)}
    assert comparisons["a"].regressed is True
    assert comparisons["a"].delta == -0.6
    assert comparisons["b"].regressed is False
    assert comparisons["b"].delta == 0.4
    assert has_regression(list(comparisons.values())) is True


def test_new_case_is_not_a_regression() -> None:
    comparisons = compare_to_baseline([_score("fresh", 0.0)], {"old": 1.0})
    assert comparisons[0].is_new is True
    assert comparisons[0].regressed is False
    assert has_regression(comparisons) is False


def test_within_tolerance_is_not_a_regression() -> None:
    comparisons = compare_to_baseline([_score("a", 0.9995)], {"a": 1.0}, tolerance=0.001)
    assert comparisons[0].regressed is False


def test_comparison_markdown_marks_regressions() -> None:
    md = comparison_to_markdown(compare_to_baseline([_score("a", 0.2)], {"a": 1.0}))
    assert "REGRESSED" in md
    assert "1 regression(s)" in md
