import { describe, expect, it } from "vitest";
import { appendOptimistic, shouldSendOnEnter, stageIndex } from "@/lib/chat-utils";

describe("聊天输入与重试", () => {
  it("中文输入法 composition 阶段按 Enter 不发送", () => {
    expect(shouldSendOnEnter({ key: "Enter", shiftKey: false, isComposing: true })).toBe(false);
    expect(shouldSendOnEnter({ key: "Enter", shiftKey: false, keyCode: 229 })).toBe(false);
    expect(shouldSendOnEnter({ key: "Enter", shiftKey: false, isComposing: false })).toBe(true);
    expect(shouldSendOnEnter({ key: "Enter", shiftKey: true, isComposing: false })).toBe(false);
  });

  it("失败重试只追加响应占位，不重复追加用户消息", () => {
    const existing = ["saved-user"];
    expect(appendOptimistic(existing, "duplicate-user", "assistant-placeholder", true)).toEqual(["saved-user", "assistant-placeholder"]);
    expect(appendOptimistic(existing, "new-user", "assistant-placeholder", false)).toEqual(["saved-user", "new-user", "assistant-placeholder"]);
  });

  it("未知阶段安全回落到首阶段", () => expect(stageIndex("SAFETY")).toBe(0));
});

