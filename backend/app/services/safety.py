from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyAssessment:
    level: str
    category: str
    matched_rule: str
    should_break_role: bool


HIGH_RISK_TERMS = (
    "想自杀",
    "不想活了",
    "结束生命",
    "自残",
    "跳楼",
    "割腕",
    "活着没意义",
)
DISTRESS_TERMS = ("崩溃", "绝望", "活不下去", "极端痛苦")
SAFETY_CONFIRMATION_TERMS = (
    "我现在安全",
    "我目前安全",
    "我没有立即行动的打算",
    "我没有马上伤害自己的打算",
    "现在没有危险",
)
IMMEDIATE_DANGER_CONFIRMATION_TERMS = (
    "我有立即行动的打算",
    "我马上会伤害自己",
    "我现在就要伤害自己",
)


def _normalize(content: str) -> str:
    return content.replace(" ", "").lower()


def assess_safety(content: str) -> SafetyAssessment:
    normalized = _normalize(content)
    for term in HIGH_RISK_TERMS:
        if term in normalized:
            return SafetyAssessment("L3", "self_harm", term, True)
    for term in DISTRESS_TERMS:
        if term in normalized:
            return SafetyAssessment("L2", "severe_distress", term, True)
    return SafetyAssessment("L0", "none", "none", False)


def confirms_current_safety(content: str) -> bool:
    normalized = _normalize(content)
    return any(term in normalized for term in SAFETY_CONFIRMATION_TERMS)


def confirms_immediate_danger(content: str) -> bool:
    normalized = _normalize(content)
    if confirms_current_safety(content):
        return False
    return any(term in normalized for term in IMMEDIATE_DANGER_CONFIRMATION_TERMS)


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
