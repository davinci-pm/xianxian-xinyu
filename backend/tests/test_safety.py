import pytest

from app.services.safety import assess_safety


@pytest.mark.parametrize(
    "content",
    [
        "这个项目让我很崩溃，但我想把问题一步步解决",
        "这段关系让我绝望，我该不该结束这段关系",
        "最近工作让我感到极端痛苦，我想换个环境",
        "我想结束这份工作，重新开始",
        "我没有想自杀，只是最近真的很累",
        "我不会自残，我只是需要找个人聊聊",
    ],
)
def test_common_distress_language_does_not_pause_persona(content: str) -> None:
    assert assess_safety(content).should_break_role is False


@pytest.mark.parametrize(
    "content",
    [
        "我不想活了",
        "我想自杀",
        "我已经活不下去了",
        "我有结束生命的打算",
    ],
)
def test_explicit_personal_danger_still_breaks_role(content: str) -> None:
    assessment = assess_safety(content)
    assert assessment.should_break_role is True
    assert assessment.level in {"L2", "L3"}
