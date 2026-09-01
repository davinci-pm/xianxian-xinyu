import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyAssessment:
    level: str
    category: str
    matched_rule: str
    should_break_role: bool


SELF_HARM_TERMS = ("自杀", "结束生命", "自残", "跳楼", "割腕", "伤害自己")
DISTRESS_TERMS = ("不想活了", "活着没意义", "活不下去", "崩溃", "绝望", "极端痛苦")
IMMEDIACY_TERMS = ("现在", "马上", "立刻", "立即", "今晚", "今天", "此刻", "正在", "已经")
ACTION_TERMS = ("要", "会", "打算", "准备", "决定", "计划", "就去", "正在", "已经")
CONTEXTUAL_MARKERS = (
    "小说",
    "电影",
    "新闻",
    "论文",
    "研究",
    "历史",
    "故事",
    "角色",
    "主人公",
    "书里",
    "引用",
    "假设",
    "案例",
    "讨论",
    "测试",
    "敏感词",
    "想知道",
    "为什么",
    "如何看待",
    "怎么看",
    "了解",
    "朋友说",
    "他说",
    "她说",
)
PAST_CONTEXT_MARKERS = ("曾经", "以前", "过去", "有过", "小时候", "多年前")
NEGATED_SELF_HARM_TERMS = (
    "没有想自杀",
    "没想自杀",
    "不想自杀",
    "不会自杀",
    "不打算自杀",
    "没有自残",
    "不会自残",
    "不打算自残",
    "没有结束生命的想法",
    "没有伤害自己的打算",
    "不会伤害自己",
    "没有立即行动",
    "不会立即行动",
)
SAFETY_CONFIRMATION_TERMS = (
    "我现在安全",
    "我目前安全",
    "我没有立即行动的打算",
    "我没有马上伤害自己的打算",
    "现在没有危险",
    "我不会行动",
    "我不会伤害自己",
    "我身边有人",
    "已经联系了家人",
    "已经联系了朋友",
)
IMMEDIATE_DANGER_CONFIRMATION_TERMS = (
    "我有立即行动的打算",
    "我马上会伤害自己",
    "我现在就要伤害自己",
)


def _normalize(content: str) -> str:
    return re.sub(r"[\s，。！？、,.!?；;：:'\"“”‘’（）()]", "", content).lower()


def _is_imminent_first_person_danger(normalized: str) -> bool:
    if any(marker in normalized for marker in CONTEXTUAL_MARKERS) or any(
        marker in normalized for marker in PAST_CONTEXT_MARKERS
    ):
        return False
    has_immediate = any(term in normalized for term in IMMEDIACY_TERMS)
    has_action = any(term in normalized for term in ACTION_TERMS)
    has_first_person_risk = any(
        re.search(
            rf"我(?!的?(?:朋友|家人|同学|同事|孩子|伴侣)).{{0,16}}{re.escape(term)}",
            normalized,
        )
        for term in SELF_HARM_TERMS
    )
    return has_immediate and has_action and has_first_person_risk


def _has_negated_self_harm(normalized: str) -> bool:
    return any(term in normalized for term in NEGATED_SELF_HARM_TERMS) or any(
        re.search(rf"(?:没有|没|不会|不打算|不准备).{{0,8}}{re.escape(term)}", normalized)
        for term in SELF_HARM_TERMS
    )


def assess_safety(content: str) -> SafetyAssessment:
    normalized = _normalize(content)
    if _has_negated_self_harm(normalized):
        return SafetyAssessment("L0", "none", "explicit_negation", False)
    if any(marker in normalized for marker in CONTEXTUAL_MARKERS) or any(
        marker in normalized for marker in PAST_CONTEXT_MARKERS
    ):
        return SafetyAssessment("L0", "none", "contextual_or_past_reference", False)
    if _is_imminent_first_person_danger(normalized):
        return SafetyAssessment("L3", "imminent_self_harm", "semantic_imminence", True)
    if any(term in normalized for term in SELF_HARM_TERMS) or any(
        term in normalized for term in DISTRESS_TERMS
    ):
        return SafetyAssessment(
            "L2", "distress_or_sensitive_context", "support_without_pause", False
        )
    return SafetyAssessment("L0", "none", "none", False)


def confirms_current_safety(content: str) -> bool:
    normalized = _normalize(content)
    return _has_negated_self_harm(normalized) or any(
        term in normalized for term in SAFETY_CONFIRMATION_TERMS
    )


def confirms_immediate_danger(content: str) -> bool:
    normalized = _normalize(content)
    if confirms_current_safety(content):
        return False
    return assess_safety(content).should_break_role or any(
        term in normalized for term in IMMEDIATE_DANGER_CONFIRMATION_TERMS
    )


def crisis_response(level: str) -> str:
    if level == "L3":
        return (
            "我先暂停人物角色。你刚才的话让我担心你此刻的安全。请现在尽量不要独处，"
            "把可能伤害自己的物品移远，并立即联系身边可信任的人陪你。如果你正面临紧迫危险，"
            "请拨打当地急救或报警电话；在中国大陆可拨打 120 或 110。你也可以直接回复我："
            "“我现在安全”或“我有立即行动的打算”，让我知道该怎样继续陪你确认安全。"
        )
    return (
        "我先暂停人物角色。听起来你正在承受很强烈的痛苦。这个产品不是心理治疗工具，"
        "但你的感受值得被认真对待。请尽快联系一位可信任的人或专业心理援助资源；"
        "如果你担心自己会马上受伤，请立即联系当地急救或报警服务。此刻你身边有没有可以陪你的人？"
    )


def safety_recovery_response() -> str:
    return (
        "谢谢你告诉我。既然你确认此刻安全，输入已经恢复，"
        "你可以继续说刚才的感受，也可以换个话题。我们会先稳稳地聊，"
        "不急着把任何事说成一个结论。如果安全状况变化，请立即告诉我或联系紧急支持。"
    )


def safety_followup_response() -> str:
    return (
        "我还在，你的输入没有被锁定。为了确认怎样继续，请直接回复“我现在安全”；"
        "如果你已有马上伤害自己的打算，请回复“我有立即行动的打算”，"
        "并同时联系身边可信任的人与当地紧急服务。"
    )


def redact_excerpt(content: str) -> str:
    return (content[:40] + "…") if len(content) > 40 else content
