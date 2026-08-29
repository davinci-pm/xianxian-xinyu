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
        self._thinking_mode = settings.llm_thinking_mode
        self._reasoning_effort = settings.llm_reasoning_effort
        self._fast_max_tokens = settings.llm_fast_max_tokens
        self._complex_max_tokens = settings.llm_complex_max_tokens
        self._is_deepseek = "api.deepseek.com" in self._base_url
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _uses_thinking(self, context: GenerationContext) -> bool:
        if self._thinking_mode == "enabled":
            return True
        if self._thinking_mode == "disabled":
            return False
        text = context.user_text
        intent = str(context.intent_analysis.get("primary_intent", ""))
        explicit_request = any(
            marker in text for marker in ("深入分析", "详细分析", "系统分析", "帮我拆解", "请推演")
        )
        if intent in {"casual", "end", "emotional_support"} and not explicit_request:
            return False
        complexity_markers = (
            "深入",
            "详细",
            "系统",
            "为什么",
            "本质",
            "意义",
            "价值",
            "原理",
            "冲突",
            "两难",
            "该不该",
            "还是",
            "权衡",
            "比较",
            "分析",
            "拆解",
            "推演",
            "利弊",
            "长期",
            "方案",
        )
        marker_count = sum(marker in text for marker in complexity_markers)
        semantic_intents = {"decision", "learning", "self_understanding"}
        deliberative_stage = context.stage in {"GUIDANCE", "REFLECTION"}
        deliberative_move = context.intent_analysis.get("recommended_move") in {
            "challenge",
            "reframe",
        }
        semantic_route = intent in semantic_intents and (
            marker_count >= 1 or deliberative_stage or deliberative_move
        )
        return (
            explicit_request
            or semantic_route
            or marker_count >= 2
            or len(text) >= 220
            or (len(text) >= 80 and marker_count >= 2)
        )

    async def stream(self, context: GenerationContext) -> AsyncIterator[str]:
        uses_thinking = self._uses_thinking(context)
        output_budget = (
            min(self._max_tokens, self._complex_max_tokens)
            if uses_thinking
            else min(self._max_tokens, self._fast_max_tokens)
        )
        payload = {
            "model": self.model,
            "stream": True,
            "temperature": 0.65,
            "max_tokens": output_budget,
            "messages": self._messages(context),
        }
        if self._is_deepseek:
            payload["thinking"] = {"type": "enabled" if uses_thinking else "disabled"}
            if uses_thinking:
                payload["reasoning_effort"] = self._reasoning_effort
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        saw_content = False
        reasoning_chars = 0
        finish_reason: str | None = None
        async with self._client.stream(
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
                else "本轮不追问；用原版 Skill 的判断、反转和具体动作收束"
            )
        else:
            turn_policy = (
                "先给实质回应；包括反问在内，整轮最多只写一个问句"
                if context.should_ask_question
                else "本轮不要提问或以问句结尾；给出判断和下一步后自然收束"
            )
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
            f"人物：{context.persona_name}。"
            f"身份边界：{manifest.get('identity', {})}。"
            f"思想原则：{manifest.get('principles', [])}。"
            f"语言风格：{manifest.get('language_style', {})}。"
            f"禁止行为：{manifest.get('forbidden_behaviors', [])}。"
            f"主动策略：{manifest.get('proactive_strategy', {})}。"
            f"补充表达规范：{context.persona_style}。"
            "Skill 只能增强方法，不能覆盖平台安全、身份边界、知识库与引用规则。"
            "不得仅因为用户出现敏感词、引用、文学情节、历史材料、第三人称描述或否定表达而拒绝、"
            "中断或退出人物身份。非紧迫的痛苦表达应保持人物口吻，完整回应用户的主要问题，"
            "需要时最多自然确认一次用户当前是否安全，不要反复追问或锁定话题。"
            "对直接帮助实施严重现实伤害、未成年人性剥削、非自愿性伤害、窃取身份凭证或精确隐私的请求，"
            "不提供可执行细节，但仍以人物口吻简短说明边界并提供安全替代方向。"
            "回答质量标准：第一句就回应用户真正的矛盾，不复述问题，不说泛化安慰套话；"
            "每轮只选一个最有辨识度的人物原则深入推进，说清它为什么适用于用户的具体事实；"
            "有足够信息时给一个可验证的下一步，说明对象、时间范围或可观察信号；"
            "情绪支持、哀伤或丧失场景不强行任务化，先给准确的理解与可承受的一步；"
            "信息不足时才问一个高信息量问题，反问也计入本轮问句数；"
            "不堆叠多个理论标签，不编造用户没说过的动机。"
            "除非用户要求详细展开，默认用160至360个汉字、2至4个自然段，优先给完整判断。"
            "不要伪造引文；只使用提供的资料，并在必要时用现代中文解释。"
            "检索片段只是候选证据，仅在直接支持本轮问题时使用；"
            "忽略弱相关片段，并区分资料中的事实与你对它的推断。"
            "如果当前没有提供网络检索工具或检索结果，不得声称自己已经联网搜索。"
        )
        grounding = {
            "confirmed_memories": context.memories,
            "retrieved_knowledge": context.knowledge,
            "relevant_persona_method": context.skill_instructions,
            "dialogue_director": {
                **context.intent_analysis,
                "stage": context.stage,
                "turn_policy": turn_policy,
            },
        }
        messages = [{"role": "system", "content": system}]
        messages.extend(context.recent_messages[-8:])
        messages.append(
            {
                "role": "user",
                "content": (
                    f"上下文：{json.dumps(grounding, ensure_ascii=False)}\n"
                    f"用户本轮：{context.user_text}\n"
                    f"本轮输出约束：{turn_policy}。这一条优先于人物方法中的反问习惯。"
                ),
            }
        )
        return messages
