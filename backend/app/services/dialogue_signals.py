import re

EXACT_END_PHRASES = {
    "先这样",
    "今天先这样",
    "不聊了",
    "谢谢不用了",
    "我想停下",
    "结束",
    "结束吧",
    "到这里吧",
    "就这样吧",
}
CONVERSATION_END_PHRASES = (
    "下次再聊",
    "今天就到这里",
    "今天先聊到这里",
    "先聊到这里",
    "结束对话",
    "结束聊天",
    "结束本次对话",
    "结束这次对话",
)


def is_explicit_end(content: str) -> bool:
    normalized = re.sub(r"[\s，。！？、,.!?；;：:]", "", content).lower()
    if normalized in EXACT_END_PHRASES:
        return True
    return any(phrase in normalized for phrase in CONVERSATION_END_PHRASES)
