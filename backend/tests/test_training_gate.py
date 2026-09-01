from app.services.training_gate import assess_lora_need


def _health(turns: int = 500) -> dict:
    return {
        "adaptive_tier": "trainable",
        "data_profile": {"contextual_target_turns": turns},
    }


def test_lora_gate_rejects_small_or_unsafe_datasets() -> None:
    small = assess_lora_need(
        {"adaptive_tier": "structured", "data_profile": {"contextual_target_turns": 80}}
    )
    unsafe = assess_lora_need(
        _health(),
        {
            "evaluated_cases": 50,
            "boundary_pass_rate": 0.9,
            "semantic_score": 0.8,
            "voice_score": 0.4,
        },
    )

    assert small["decision"] == "defer"
    assert unsafe["decision"] == "defer"


def test_lora_gate_only_recommends_style_residual_after_content_passes() -> None:
    recommended = assess_lora_need(
        _health(),
        {
            "evaluated_cases": 50,
            "boundary_pass_rate": 1.0,
            "semantic_score": 0.78,
            "voice_score": 0.51,
        },
    )
    already_good = assess_lora_need(
        _health(),
        {
            "evaluated_cases": 50,
            "boundary_pass_rate": 1.0,
            "semantic_score": 0.8,
            "voice_score": 0.76,
        },
    )

    assert recommended["decision"] == "recommend"
    assert recommended["training_policy"]["exclude_holdout"] is True
    assert already_good["decision"] == "not_needed"
