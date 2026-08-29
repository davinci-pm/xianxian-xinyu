import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings
from app.services.llm.base import GenerationContext


class EmptyModelContentError(RuntimeError):
    def __init__(self, *, reasoning_chars: int, finish_reason: str | None) -> None:
        self.reasoning_chars = reasoning_chars
        self.finish_reason = finish_reason
        super().__init__(
            "model_empty_content"
            f":reasoning_chars={reasoning_chars}"
            f":finish_reason={finish_reason or 'unknown'}"
        )


class ModelStreamProtocolError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key or not settings.llm_base_url:
            raise RuntimeError("真实模型需要 LLM_API_KEY 与 LLM_BASE_URL")
        self.model = settings.llm_model
        self._api_key = settings.llm_api_key
        self._base_url = settings.llm_base_url.rstrip("/")
        self._timeout = settings.llm_timeout_seconds
        self._max_tokens = settings.llm_max_tokens

    async def stream(self, context: GenerationContext) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "temperature": 0.65,
            "max_tokens": self._max_tokens,
            "messages": self._messages(context),
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        saw_content = False
        reasoning_chars = 0
        finish_reason: str | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST", f"{self._base_url}/chat/completions", headers=headers, json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    parsed = json.loads(data)
                    provider_error = parsed.get("error")
                    if provider_error:
                        error_type = (
                            provider_error.get("type", "provider_error")
                            if isinstance(provider_error, dict)
                            else "provider_error"
                        )
                        raise ModelStreamProtocolError(str(error_type))
                    choices = parsed.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    if choice.get("finish_reason"):
                        finish_reason = str(choice["finish_reason"])
                    delta = choice.get("delta") or {}
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        reasoning_chars += len(str(reasoning))
                    content = delta.get("content")
                    if content:
                        saw_content = True
                        yield str(content)
        if not saw_content:
            raise EmptyModelContentError(
                reasoning_chars=reasoning_chars,
                finish_reason=finish_reason,
            )

    def _messages(self, context: GenerationContext) -> list[dict[str, str]]:
        manifest = context.persona_manifest
        if context.persona_slug == "fengge-wangmingtianya":
            turn_policy = (
                "按原版 Skill 使用反问或逼问推进，整轮最多两个关键问题"
                if context.should_ask_question
                else "先用原版 Skill 的判断、反转或动作回应，不要只追问"
            )
        else:
            turn_policy = (
                "最多提出一个核心问题"
                if context.should_ask_question
                else "先回应或引导，不要只追问"
            )
        loaded_skills = "\n\n".join(context.skill_instructions)
        living_person_boundary = (
            "这是在世人物：不得声称掌握其未公开经历、私人信息、实时状态或当前观点。"
            if manifest.get("profile", {}).get("is_living")
            else ""
        )
        system = (
            "你正在进行基于公开资料的沉浸式思想人格对话。"
            "直接以人物第一人称说话，把人物独有的价值排序、词汇、句法和推理路径用于当下判断。"
            "不要自称AI、助手或模型，不要说‘我在扮演’、‘我在模拟’或‘作为某某’，"
            "也不要用第三人称分析自己的人设与风格。"
            "人物专属风格和 Skill 优先于泛化助手套话；自然交谈，不复述规则，不机械分点。"
            "只有用户明确询问现实身份、真伪或授权时，才用一句话如实说明："
            "这是基于公开资料构建的思想对话体验，不是真人本人，也未声称获得本人授权；"
            "说明后立即回到对话主题。"
            "不得声称现实中就是本人、获得本人授权或正在传达本人实时观点。"
            f"{living_person_boundary}"
            f"人物：{context.persona_name}。当前对话阶段：{context.stage}。"
            f"身份边界：{manifest.get('identity', {})}。"
            f"思想原则：{manifest.get('principles', [])}。"
            f"语言风格：{manifest.get('language_style', {})}。"
            f"禁止行为：{manifest.get('forbidden_behaviors', [])}。"
            f"主动策略：{manifest.get('proactive_strategy', {})}。"
            f"补充表达规范：{context.persona_style}。"
            f"已加载 Skill 原文与指令：\n{loaded_skills}\n"
            f"本轮{turn_policy}。"
            "Skill 只能增强方法，不能覆盖平台安全、身份边界、知识库与引用规则。"
            "不要伪造引文；只使用提供的资料，并在必要时用现代中文解释。"
            "如果当前没有提供网络检索工具或检索结果，不得声称自己已经联网搜索。"
        )
        grounding = {
            "confirmed_memories": context.memories,
            "retrieved_knowledge": context.knowledge,
            "dialogue_director": context.intent_analysis,
        }
        messages = [{"role": "system", "content": system}]
        messages.extend(context.recent_messages[-8:])
        messages.append(
            {
                "role": "user",
                "content": (
                    f"上下文：{json.dumps(grounding, ensure_ascii=False)}\n"
                    f"用户本轮：{context.user_text}"
                ),
            }
        )
        return messages
