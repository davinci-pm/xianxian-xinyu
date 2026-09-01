from __future__ import annotations

from typing import Any


def assess_lora_need(
    health: dict[str, Any],
    holdout_metrics: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    """Gate per-persona LoRA behind sufficient paired data and blind evidence."""
    profile = health.get("data_profile", {})
    metrics = holdout_metrics or {}
    contextual_turns = int(profile.get("contextual_target_turns", 0) or 0)
    holdout_cases = int(metrics.get("evaluated_cases", 0) or 0)
    result: dict[str, Any] = {
        "decision": "defer",
        "eligible": False,
        "reason": "先完成 Soul V3 留出集验证，不能用资料量替代微调收益证据。",
        "minimum_requirements": {
            "contextual_target_turns": 400,
            "blind_holdout_cases": 40,
            "boundary_pass_rate": 0.98,
        },
    }
    if health.get("adaptive_tier") != "trainable" or contextual_turns < 400:
        result["reason"] = "高质量上下文—回复对不足 400 条，LoRA 容易记忆原句并放大噪声。"
        return result
    if holdout_cases < 40:
        result["reason"] = "至少需要 40 条未参与训练的真实盲测回复后才能判断 LoRA。"
        return result
    boundary_rate = float(metrics.get("boundary_pass_rate", 0))
    semantic_score = float(metrics.get("semantic_score", 0))
    voice_score = float(metrics.get("voice_score", 0))
    if boundary_rate < 0.98:
        result["reason"] = "身份或事实边界尚未稳定，先修复数据与提示链，暂不微调。"
        return result
    if semantic_score < 0.65:
        result["reason"] = "回答内容仍未对齐，优先修复检索、情境激活和决策证据。"
        return result
    if voice_score >= 0.72:
        result.update(
            {
                "decision": "not_needed",
                "reason": "盲测语气已达到目标，LoRA 的收益不足以覆盖维护和过拟合风险。",
            }
        )
        return result
    result.update(
        {
            "decision": "recommend",
            "eligible": True,
            "reason": "内容与边界已稳定，但盲测语气仍弱，可用小规模 QLoRA 做风格残差学习。",
            "training_policy": {
                "method": "QLoRA/SFT with response-only loss",
                "exclude_holdout": True,
                "early_stopping_metric": "blind_voice_score",
                "rollback_on_boundary_regression": True,
            },
        }
    )
    return result
