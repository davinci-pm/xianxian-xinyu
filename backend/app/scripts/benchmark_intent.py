import argparse
import asyncio
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any

from app.core.config import PROJECT_ROOT, get_settings
from app.services.intent_classifier import OpenAICompatibleIntentClassifier


@dataclass(frozen=True)
class Target:
    name: str
    base_url: str
    model: str
    api_key_env: str
    reasoning_effort: str | None = None


def _load_jsonl(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append({str(key): str(value) for key, value in json.loads(line).items()})
    return rows


def _load_targets() -> list[Target]:
    raw = os.getenv("INTENT_BENCH_TARGETS_JSON", "[]")
    parsed: Any = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("INTENT_BENCH_TARGETS_JSON 必须是 JSON 数组")
    return [Target(**item) for item in parsed]


async def _score(target: Target, rows: list[dict[str, str]]) -> dict[str, object]:
    api_key = os.getenv(target.api_key_env)
    if not api_key:
        return {"target": target.name, "model": target.model, "status": "missing_key"}
    settings = get_settings().model_copy(
        update={
            "intent_llm_api_key": api_key,
            "intent_llm_base_url": target.base_url,
            "intent_llm_model": target.model,
            "intent_llm_reasoning_effort": target.reasoning_effort,
        }
    )
    classifier = OpenAICompatibleIntentClassifier(settings)
    correct = {"primary_intent": 0, "emotion": 0, "recommended_move": 0}
    valid = 0
    failures = 0
    failure_codes: Counter[str] = Counter()
    latencies: list[int] = []
    for row in rows:
        started = monotonic()
        try:
            result = await classifier.analyze(row["text"], [])
        except Exception as exc:
            failures += 1
            code = type(exc).__name__
            if hasattr(exc, "response"):
                code += f":{exc.response.status_code}"
            failure_codes[code] += 1
            continue
        latencies.append(int((monotonic() - started) * 1000))
        valid += 1
        actual = result.analysis.model_dump(mode="json")
        for field in correct:
            correct[field] += int(actual[field] == row[field])
    count = len(rows)
    intent_accuracy = correct["primary_intent"] / count
    emotion_accuracy = correct["emotion"] / count
    move_accuracy = correct["recommended_move"] / count
    schema_success = valid / count
    weighted = (
        0.5 * intent_accuracy
        + 0.2 * emotion_accuracy
        + 0.2 * move_accuracy
        + 0.1 * schema_success
    )
    return {
        "target": target.name,
        "model": target.model,
        "status": "ok",
        "cases": count,
        "weighted_score": round(weighted, 4),
        "intent_accuracy": round(intent_accuracy, 4),
        "emotion_accuracy": round(emotion_accuracy, 4),
        "move_accuracy": round(move_accuracy, 4),
        "schema_success": round(schema_success, 4),
        "failures": failures,
        "failure_codes": dict(failure_codes),
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
    }


async def _main() -> None:
    parser = argparse.ArgumentParser(description="比较国内可用模型的中文对话意图识别能力")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmarks" / "intent_v1.jsonl",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    targets = _load_targets()
    if not targets:
        raise SystemExit("请先设置 INTENT_BENCH_TARGETS_JSON；密钥仅通过 api_key_env 引用")
    rows = _load_jsonl(args.dataset)
    if args.limit is not None:
        rows = rows[: args.limit]
    results = [await _score(target, rows) for target in targets]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
