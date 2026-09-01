// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import type { NoteRecord } from "@/lib/local-data";
import { buildNoteDocxBlob, buildNoteMarkdown, buildNotePrintHtml, parseNoteBody } from "@/lib/note-export";
import type { ConversationDetail } from "@/lib/types";

const note: NoteRecord = {
  id: "note-1",
  conversationId: "conversation-1",
  personaSlug: "confucius",
  personaName: "孔子",
  title: "与孔子谈过之后",
  summary: "把选择落到行动",
  body: "## 我带来的困惑\n\n我不知道该不该转行。\n\n## 我想带走的一步\n\n- 本周访谈一位从业者",
  themes: ["选择", "行动"],
  memories: ["我计划转行"],
  createdAt: "2026-08-29T00:00:00.000Z",
  updatedAt: "2026-08-29T00:00:00.000Z",
};

const conversation = {
  id: "conversation-1",
  messages: [
    { id: "m1", role: "user", content: "我不知道该不该转行。", citations: [], created_at: "2026-08-29T00:00:00.000Z" },
    { id: "m2", role: "assistant", content: "先做一件可以验证的小事。", citations: [{ document_id: "d1", label: "《论语》", source_url: "https://example.test/analects" }], created_at: "2026-08-29T00:00:01.000Z" },
  ],
} as ConversationDetail;

describe("心语札记导出", () => {
  it("默认导出精简札记，完整对话只在勾选后追加", () => {
    const concise = buildNoteMarkdown({ note, conversation, includeTranscript: false });
    expect(concise).toContain("## 我带来的困惑");
    expect(concise).toContain("## 参考资料");
    expect(concise).not.toContain("## 完整对话记录");

    const full = buildNoteMarkdown({ note, conversation, includeTranscript: true });
    expect(full).toContain("## 完整对话记录");
    expect(full).toContain("先做一件可以验证的小事");
  });

  it("将札记 Markdown 转换为结构化内容", () => {
    expect(parseNoteBody(note.body)).toEqual([
      { type: "heading", level: 2, text: "我带来的困惑" },
      { type: "paragraph", text: "我不知道该不该转行。" },
      { type: "heading", level: 2, text: "我想带走的一步" },
      { type: "bullet", text: "本周访谈一位从业者" },
    ]);
  });

  it("生成可下载的 Word 文件与适合打印的 PDF 页面", async () => {
    const blob = await buildNoteDocxBlob({ note, conversation, includeTranscript: true });
    expect(blob.size).toBeGreaterThan(2_000);
    expect(blob.type).toContain("wordprocessingml");

    const html = buildNotePrintHtml({ note, conversation, includeTranscript: true });
    expect(html).toContain("@page { size: A4");
    expect(html).toContain("完整对话记录");
    expect(html).not.toContain("<script");
  });
});
