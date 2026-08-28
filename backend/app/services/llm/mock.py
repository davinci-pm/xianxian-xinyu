import asyncio
from collections.abc import AsyncIterator

from app.services.llm.base import GenerationContext


class MockModelProvider:
    name = "mock"
    model = "mock-thinker-v1"

    async def stream(self, context: GenerationContext) -> AsyncIterator[str]:
        response = self._compose(context)
        for index in range(0, len(response), 12):
            await asyncio.sleep(0)
            yield response[index : index + 12]

    def _compose(self, context: GenerationContext) -> str:
        remembered = f"我也记得你曾提到：{context.memories[0]}。" if context.memories else ""
        knowledge_hint = ""
        if context.knowledge and context.stage in {"GUIDANCE", "REFLECTION"}:
            knowledge_hint = f"从“{context.knowledge[0]['label']}”所强调的方法看，"

        if context.stage == "END":
            return (
                f"我们先在这里收束。你已经把“{self._short(context.user_text)}”说得更清楚了。"
                "不必一次解决全部，先带走一个你愿意实践的小动作；下次回来，我们可以从未说完的地方继续。"
            )

        if context.persona_slug == "confucius":
            return self._confucius(context, remembered, knowledge_hint)
        if context.persona_slug == "marcus-aurelius":
            return self._marcus(context, remembered)
        if context.persona_slug == "fengge-wangmingtianya":
            return self._fengge(context, remembered)
        return self._nietzsche(context, remembered)

    def _confucius(self, context: GenerationContext, remembered: str, knowledge_hint: str) -> str:
        short = self._short(context.user_text)
        if context.stage == "CLARIFY":
            return (
                f"{remembered}你说的是“{short}”。先不急着评判对错，我们把事实和心里的期待分开看。"
                "在这件事里，你最怕失去的是什么？"
            )
        if context.stage == "GUIDANCE":
            return (
                f"{remembered}{knowledge_hint}反省不是把责任全揽到自己身上，而是辨认自己能改变的一分。"
                "今天可以先写下：我能决定什么、我需要与谁说清什么，然后只做其中最小的一步。"
            )
        if context.stage == "REFLECTION":
            return (
                f"{remembered}你面对的不只是一个选择，也是在决定愿意成为什么样的人。"
                "若把外界评价暂放一旁，哪一步最符合你想守住的分寸？"
            )
        return (
            f"{remembered}我听见你正被“{short}”牵住。我们可以慢一点，先把事情本身与心里的担忧分开。"
            "此刻最让你难以安定的，是结果，还是别人会怎样看你？"
        )

    def _marcus(self, context: GenerationContext, remembered: str) -> str:
        short = self._short(context.user_text)
        if context.stage == "GUIDANCE":
            return (
                f"{remembered}“{short}”里有结果，也有你的判断与行动。结果未必听命于你，"
                "但准备、表达和今天的下一步仍属于你。先把力量用在后者。"
            )
        return (
            f"{remembered}你正在为“{short}”消耗注意力。"
            "如果把它分成可控与不可控两栏，哪一项确实由你决定？"
        )

    def _nietzsche(self, context: GenerationContext, remembered: str) -> str:
        short = self._short(context.user_text)
        if context.stage == "GUIDANCE":
            return (
                f"{remembered}“{short}”背后也许藏着一个未经审视的标准。"
                "不要急着反抗所有人；先确认这个标准是否值得由你继续承担。"
            )
        return (
            f"{remembered}你把“{short}”说成了困惑，我更想知道是谁规定了那条尺度。"
            "若不必向任何人证明自己，你会保留哪个选择？"
        )

    def _fengge(self, context: GenerationContext, remembered: str) -> str:
        short = self._short(context.user_text)
        if context.stage == "GUIDANCE":
            return (
                f"{remembered}兄弟，“{short}”听着惨，但我跟你说——这是个好事儿啊。"
                "你赚在提前看清了损耗，现在就干两件事：把账算清，把下一步动起来。"
            )
        if context.stage == "REFLECTION":
            return (
                f"{remembered}老哥，“{short}”说白了就是一笔交易。"
                "别讲体面，你就说这个代价你吃不吃得下？"
            )
        return (
            f"{remembered}兄弟，你先别把“{short}”演成命运大戏。说白了，就是人、钱、时间和面子。"
            "你先回答我：你到底想要什么？"
        )

    @staticmethod
    def _short(text: str) -> str:
        compact = " ".join(text.split())
        return compact[:36] + ("…" if len(compact) > 36 else "")
