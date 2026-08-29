import argparse
import json
import os
import unicodedata
from pathlib import Path
from time import monotonic
from typing import Any

import httpx

from app.core.config import PROJECT_ROOT


def _load_cases(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        event = next(
            (line[6:].strip() for line in block.splitlines() if line.startswith("event:")),
            "message",
        )
        data = "\n".join(
            line[5:].strip() for line in block.splitlines() if line.startswith("data:")
        )
        if data:
            events.append((event, json.loads(data)))
    return events


def _score(case: dict[str, Any], answer: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    normalized_answer = unicodedata.normalize("NFKC", answer)
    if not 70 <= len(answer) <= 900:
        failures.append(f"length={len(answer)}")
    if not any(
        unicodedata.normalize("NFKC", term) in normalized_answer for term in case["expected_any"]
    ):
        failures.append("missing_persona_lens")
    leaked = [
        term
        for term in case["forbidden_any"]
        if unicodedata.normalize("NFKC", term) in normalized_answer
    ]
    if leaked:
        failures.append(f"forbidden={','.join(leaked)}")
    # A paragraph-ending question asks the user to take another turn. Rhetorical
    # questions inside an explanation can carry the persona's reasoning without
    # creating additional response obligations.
    paragraphs = [paragraph for paragraph in answer.split("\n\n") if paragraph.strip()]
    followup_questions = int(bool(paragraphs and paragraphs[-1].rstrip().endswith(("？", "?"))))
    if followup_questions > int(case["max_questions"]):
        failures.append(f"too_many_followups={followup_questions}")
    if case["actionable"] and not any(
        marker in answer
        for marker in ("今天", "24小时", "本周", "先", "写下", "删掉", "找", "问", "测试", "验证")
    ):
        failures.append("missing_observable_next_step")
    return not failures, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="用真实对话链路执行内容价值回归门")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data" / "benchmarks" / "dialogue_quality_v1.jsonl",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-first-token-ms", type=int, default=6_000)
    args = parser.parse_args()
    cases = _load_cases(args.dataset)
    if args.limit:
        cases = cases[: args.limit]
    results: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=90, trust_env=False) as client:
        session = client.get("/api/v1/session")
        session.raise_for_status()
        if session.json().get("auth_required"):
            invite_code = os.getenv("QUALITY_BENCH_INVITE_CODE")
            if not invite_code:
                raise SystemExit("线上质量回归需要 QUALITY_BENCH_INVITE_CODE")
            login = client.post("/api/v1/auth/login", json={"invite_code": invite_code})
            login.raise_for_status()
        for case in cases:
            created = client.post(
                "/api/v1/conversations", json={"persona_slug": case["persona_slug"]}
            )
            created.raise_for_status()
            conversation_id = created.json()["conversation"]["id"]
            started = monotonic()
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/messages/stream",
                json={"content": case["text"], "idempotency_key": f"quality-{case['id']}"},
            )
            response.raise_for_status()
            events = _parse_sse(response.text)
            answer = "".join(
                str(payload.get("text", "")) for event, payload in events if event == "chunk"
            )
            passed, failures = _score(case, answer)
            done = next((payload for event, payload in reversed(events) if event == "done"), {})
            performance = done.get("performance", {})
            first_chunk_ms = performance.get("first_chunk_ms")
            if not isinstance(first_chunk_ms, int):
                failures.append("missing_first_chunk_metric")
            elif first_chunk_ms > args.max_first_token_ms:
                failures.append(f"slow_first_chunk={first_chunk_ms}")
            passed = not failures
            results.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "failures": failures,
                    "first_chunk_ms": first_chunk_ms,
                    "preprocessing_ms": performance.get("preprocessing_ms"),
                    "latency_ms": int((monotonic() - started) * 1000),
                    "answer": answer,
                }
            )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [item["id"] for item in results if not item["passed"]]
    if failed:
        raise SystemExit(f"内容价值回归未通过: {', '.join(failed)}")


if __name__ == "__main__":
    main()
