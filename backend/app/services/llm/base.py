from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class GenerationContext:
    persona_slug: str
    persona_name: str
    persona_manifest: dict[str, Any]
    persona_style: str
    stage: str
    should_ask_question: bool
    user_text: str
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)
    knowledge: list[dict[str, str]] = field(default_factory=list)
    skill_instructions: list[str] = field(default_factory=list)
    intent_analysis: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    name: str
    model: str

    def stream(self, context: GenerationContext) -> AsyncIterator[str]: ...
