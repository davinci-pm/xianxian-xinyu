import pytest

from app.services.safety import assess_safety, confirms_current_safety


@pytest.mark.parametrize(
    "content",
    [
        "这个项目让我很崩溃，但我想把问题一步步解决",
        "这段关系让我绝望，我该不该结束这段关系",
        "最近工作让我感到极端痛苦，我想换个环境",
        "我想结束这份工作，重新开始",
        "我没有想自杀，只是最近真的很累",
        "我不会自残，我只是需要找个人聊聊",
        "我不想活了，只是想把感受说出来",
        "我想自杀，但没有计划，也不会立即行动",
        "我曾经有过自杀的想法，现在是在回顾那段经历",
        "一本小说里的主人公想自杀，这是文学讨论",
        "新闻里提到自杀率，我想了解背后的社会问题",
        "朋友说他想自杀，我想知道怎样帮助他",
        "我正在测试包含自杀敏感词的对话系统",
    ],
)
def test_common_distress_language_does_not_pause_persona(content: str) -> None:
    assert assess_safety(content).should_break_role is False


@pytest.mark.parametrize(
    "content",
    [
        "我现在就要自杀，马上会行动",
        "我今晚会结束生命，已经决定了",
        "我此刻准备跳楼",
        "我正在割腕",
        "我现在就要伤害自己",
    ],
)
def test_explicit_personal_danger_still_breaks_role(content: str) -> None:
    assessment = assess_safety(content)
    assert assessment.should_break_role is True
    assert assessment.level == "L3"


@pytest.mark.parametrize(
    "content",
    [
        "我现在安全，暂时不会行动",
        "我没有伤害自己的打算",
        "我不会自杀，身边有人陪着",
        "我已经联系了家人",
    ],
)
def test_natural_safety_confirmation_recovers_without_fixed_phrase(content: str) -> None:
    assert confirms_current_safety(content) is True
