from app.services.chat_corpus import analyze_chat_quality, extract_target_messages, parse_chat_turns


def test_parse_wechat_like_headers_preserves_context_and_sessions() -> None:
    content = """
2026-08-01 09:00:00 小王
你觉得这个项目要继续吗？
2026-08-01 09:01:00 老孙
先看有没有用户，再谈技术领先。
2026-08-01 11:30:00 小王
那短期收入怎么办？
2026-08-01 11:31:00 老孙
如果采用率能起来，我宁愿先降费。
"""

    turns = parse_chat_turns(content)

    assert len(turns) == 4
    assert turns[1].context_before == "你觉得这个项目要继续吗？"
    assert turns[2].session_index == 1
    assert extract_target_messages(content, "老孙") == (
        "先看有没有用户，再谈技术领先。\n如果采用率能起来，我宁愿先降费。"
    )


def test_quality_separates_target_from_counterpart_and_noise() -> None:
    content = """
[2026-08-01 09:00] 小王：今天怎么安排？
[2026-08-01 09:01] 老孙：嗯
[2026-08-01 09:02] 老孙：先把用户反馈过一遍，再决定产品方向。
[2026-08-02 10:00] 系统：老孙撤回了一条消息
"""

    quality = analyze_chat_quality(content, "老孙")

    assert quality["parsed_turns"] == 3
    assert quality["target_turns"] == 2
    assert quality["substantive_target_turns"] == 1
    assert quality["counterpart_count"] == 1
