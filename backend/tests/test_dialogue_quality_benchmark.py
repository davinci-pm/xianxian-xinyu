from pathlib import Path

from app.scripts.benchmark_dialogue_quality import _load_cases, _score


def test_quality_benchmark_covers_distinct_personas_and_rubric() -> None:
    path = Path(__file__).resolve().parents[2] / "data" / "benchmarks" / "dialogue_quality_v1.jsonl"
    cases = _load_cases(path)

    assert len(cases) >= 8
    assert len({case["persona_slug"] for case in cases}) >= 8
    assert all(case["expected_any"] and case["forbidden_any"] for case in cases)


def test_quality_score_rejects_generic_or_identity_leaking_output() -> None:
    case = _load_cases(
        Path(__file__).resolve().parents[2] / "data" / "benchmarks" / "dialogue_quality_v1.jsonl"
    )[0]

    passed, failures = _score(case, "作为AI，我理解你的感受，建议你继续努力。")

    assert passed is False
    assert "missing_persona_lens" in failures
