import type { ConversationDetail } from "@/lib/types";
import type { NoteRecord } from "@/lib/local-data";

export type NoteExportFormat = "markdown" | "docx" | "pdf";

export interface NoteExportBundle {
  note: NoteRecord;
  conversation?: ConversationDetail;
  includeTranscript: boolean;
}

type NoteBlock =
  | { type: "heading"; level: 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "bullet"; text: string };

export function parseNoteBody(markdown: string): NoteBlock[] {
  const blocks: NoteBlock[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    const text = paragraph.join(" ").trim();
    if (text) blocks.push({ type: "paragraph", text });
    paragraph = [];
  };
  for (const rawLine of markdown.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) { flush(); continue; }
    if (line.startsWith("### ")) {
      flush(); blocks.push({ type: "heading", level: 3, text: line.slice(4).trim() }); continue;
    }
    if (line.startsWith("## ")) {
      flush(); blocks.push({ type: "heading", level: 2, text: line.slice(3).trim() }); continue;
    }
    if (/^[-*]\s+/.test(line)) {
      flush(); blocks.push({ type: "bullet", text: line.replace(/^[-*]\s+/, "") }); continue;
    }
    paragraph.push(line);
  }
  flush();
  return blocks;
}

function safeFileName(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, "-").replace(/\s+/g, " ").trim().slice(0, 80) || "心语札记";
}

function noteDate(note: NoteRecord) {
  return new Date(note.createdAt).toLocaleDateString("zh-CN", {
    year: "numeric", month: "long", day: "numeric",
  });
}

function uniqueCitations(conversation?: ConversationDetail) {
  if (!conversation) return [];
  const seen = new Set<string>();
  return conversation.messages.flatMap((message) => message.citations).filter((citation) => {
    const key = `${citation.label}|${citation.source_url ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function buildNoteMarkdown(bundle: NoteExportBundle) {
  const { note, conversation, includeTranscript } = bundle;
  const lines = [
    `# ${note.title}`,
    "",
    `> ${noteDate(note)} · 与 ${note.personaName} 的心语札记`,
    "",
    note.body.trim(),
  ];
  if (note.themes.length) {
    lines.push("", "## 本轮主题", "", note.themes.map((theme) => `- ${theme}`).join("\n"));
  }
  const citations = uniqueCitations(conversation);
  if (citations.length) {
    lines.push("", "## 参考资料", "");
    citations.forEach((citation) => {
      lines.push(`- ${citation.source_url ? `[${citation.label}](${citation.source_url})` : citation.label}`);
    });
  }
  if (includeTranscript && conversation) {
    lines.push("", "## 完整对话记录", "");
    conversation.messages.forEach((message) => {
      lines.push(`### ${message.role === "assistant" ? note.personaName : "我"}`, "", message.content, "");
    });
  }
  lines.push("---", "本札记由真实对话内容整理，并经用户编辑确认；人物回答基于公开资料与模型生成。", "");
  return lines.join("\n");
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function downloadNoteMarkdown(bundle: NoteExportBundle) {
  const markdown = buildNoteMarkdown(bundle);
  downloadBlob(
    new Blob([markdown], { type: "text/markdown;charset=utf-8" }),
    `${safeFileName(bundle.note.title)}.md`,
  );
}

export async function buildNoteDocxBlob(bundle: NoteExportBundle) {
  const {
    AlignmentType,
    Document,
    Footer,
    HeadingLevel,
    LevelFormat,
    Packer,
    PageNumber,
    Paragraph,
    TextRun,
  } = await import("docx");
  const { note, conversation, includeTranscript } = bundle;
  const children: InstanceType<typeof Paragraph>[] = [
    new Paragraph({
      style: "NoteTitle",
      children: [new TextRun(note.title)],
    }),
    new Paragraph({
      style: "NoteMeta",
      children: [new TextRun(`${noteDate(note)} · 与 ${note.personaName} 的心语札记`)],
    }),
  ];
  for (const block of parseNoteBody(note.body)) {
    if (block.type === "heading") {
      children.push(new Paragraph({
        heading: block.level === 2 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
        children: [new TextRun(block.text)],
      }));
    } else if (block.type === "bullet") {
      children.push(new Paragraph({
        numbering: { reference: "note-bullets", level: 0 },
        children: [new TextRun(block.text)],
      }));
    } else {
      children.push(new Paragraph({ children: [new TextRun(block.text)] }));
    }
  }
  if (note.themes.length) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("本轮主题")] }));
    note.themes.forEach((theme) => children.push(new Paragraph({
      numbering: { reference: "note-bullets", level: 0 }, children: [new TextRun(theme)],
    })));
  }
  const citations = uniqueCitations(conversation);
  if (citations.length) {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("参考资料")] }));
    citations.forEach((citation) => children.push(new Paragraph({
      numbering: { reference: "note-bullets", level: 0 },
      children: [new TextRun(citation.label), ...(citation.source_url ? [new TextRun({ text: `\n${citation.source_url}`, color: "6F665B", size: 18 })] : [])],
    })));
  }
  if (includeTranscript && conversation) {
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_1,
      pageBreakBefore: true,
      children: [new TextRun("完整对话记录")],
    }));
    conversation.messages.forEach((message) => {
      children.push(new Paragraph({
        style: "SpeakerLabel",
        children: [new TextRun(message.role === "assistant" ? note.personaName : "我")],
      }));
      children.push(new Paragraph({ children: [new TextRun(message.content)] }));
    });
  }
  children.push(new Paragraph({
    style: "NoteBoundary",
    children: [new TextRun("本札记由真实对话内容整理，并经用户编辑确认；人物回答基于公开资料与模型生成。")],
  }));
  const doc = new Document({
    creator: "先贤心语",
    title: note.title,
    description: `与 ${note.personaName} 的心语札记`,
    styles: {
      default: {
        document: {
          run: { font: "Songti SC", size: 22, color: "2B241D" },
          paragraph: { spacing: { after: 160, line: 320 } },
        },
      },
      paragraphStyles: [
        {
          id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "STKaiti", size: 30, bold: true, color: "8F3E2F" },
          paragraph: { spacing: { before: 360, after: 160 }, keepNext: true },
        },
        {
          id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "STKaiti", size: 26, bold: true, color: "8F3E2F" },
          paragraph: { spacing: { before: 280, after: 120 }, keepNext: true },
        },
        {
          id: "NoteTitle", name: "札记标题", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "STKaiti", size: 44, bold: true, color: "8F3E2F" },
          paragraph: { spacing: { before: 0, after: 160 }, keepNext: true },
        },
        {
          id: "NoteMeta", name: "札记信息", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "Songti SC", size: 19, color: "6F665B" },
          paragraph: { spacing: { after: 360 }, keepNext: true },
        },
        {
          id: "SpeakerLabel", name: "对话者", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "STKaiti", size: 22, bold: true, color: "8F3E2F" },
          paragraph: { spacing: { before: 160, after: 60 }, keepNext: true },
        },
        {
          id: "NoteBoundary", name: "札记说明", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "Songti SC", size: 18, color: "766D62", italics: true },
          paragraph: { spacing: { before: 320, after: 0 } },
        },
      ],
    },
    numbering: {
      config: [{
        reference: "note-bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 }, spacing: { after: 80, line: 300 } } },
        }],
      }],
    },
    sections: [{
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440, header: 708, footer: 708 },
        },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun({ text: "先贤心语  ·  ", color: "8B8176", size: 17 }), new TextRun({ children: [PageNumber.CURRENT], color: "8B8176", size: 17 })],
          })],
        }),
      },
      children,
    }],
  });
  return Packer.toBlob(doc);
}

export async function downloadNoteDocx(bundle: NoteExportBundle) {
  const blob = await buildNoteDocxBlob(bundle);
  downloadBlob(blob, `${safeFileName(bundle.note.title)}.docx`);
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character] ?? character);
}

function blocksToHtml(markdown: string) {
  let inList = false;
  const output: string[] = [];
  for (const block of parseNoteBody(markdown)) {
    if (block.type !== "bullet" && inList) { output.push("</ul>"); inList = false; }
    if (block.type === "heading") output.push(`<h${block.level}>${escapeHtml(block.text)}</h${block.level}>`);
    if (block.type === "paragraph") output.push(`<p>${escapeHtml(block.text)}</p>`);
    if (block.type === "bullet") {
      if (!inList) { output.push("<ul>"); inList = true; }
      output.push(`<li>${escapeHtml(block.text)}</li>`);
    }
  }
  if (inList) output.push("</ul>");
  return output.join("");
}

export function buildNotePrintHtml(bundle: NoteExportBundle) {
  const { note, conversation, includeTranscript } = bundle;
  const citations = uniqueCitations(conversation);
  const themes = note.themes.length
    ? `<section><h2>本轮主题</h2><div class="themes">${note.themes.map((theme) => `<span>${escapeHtml(theme)}</span>`).join("")}</div></section>`
    : "";
  const sources = citations.length
    ? `<section><h2>参考资料</h2><ol>${citations.map((citation) => {
      const label = escapeHtml(citation.label);
      const url = citation.source_url && /^https?:\/\//.test(citation.source_url) ? escapeHtml(citation.source_url) : null;
      return `<li>${url ? `<a href="${url}">${label}</a>` : label}</li>`;
    }).join("")}</ol></section>`
    : "";
  const transcript = includeTranscript && conversation
    ? `<section class="transcript"><h2>完整对话记录</h2>${conversation.messages.map((message) => `<article><h3>${message.role === "assistant" ? escapeHtml(note.personaName) : "我"}</h3><p>${escapeHtml(message.content)}</p></article>`).join("")}</section>`
    : "";
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(note.title)}</title><style>
    @page { size: A4; margin: 22mm 20mm 20mm; }
    * { box-sizing: border-box; }
    body { margin: 0; color: #2b241d; font-family: "Songti SC", "Noto Serif CJK SC", "Microsoft YaHei", serif; font-size: 11pt; line-height: 1.75; }
    header { margin-bottom: 28px; padding-bottom: 20px; border-bottom: 1px solid #cfc6b8; }
    h1 { margin: 0 0 8px; color: #8f3e2f; font-family: "STKaiti", "KaiTi", serif; font-size: 25pt; line-height: 1.3; }
    header p { margin: 0; color: #766d62; font-size: 9.5pt; }
    h2 { margin: 25px 0 10px; color: #8f3e2f; font-family: "STKaiti", "KaiTi", serif; font-size: 16pt; break-after: avoid; }
    h3 { margin: 18px 0 6px; color: #8f3e2f; font-size: 11pt; break-after: avoid; }
    p { margin: 0 0 12px; white-space: pre-wrap; orphans: 3; widows: 3; }
    ul, ol { margin: 4px 0 14px; padding-left: 24px; }
    li { margin-bottom: 6px; }
    a { color: #6d3324; text-decoration: none; word-break: break-all; }
    .themes { display: flex; flex-wrap: wrap; gap: 8px; }
    .themes span { padding: 3px 9px; border: 1px solid #cfc6b8; border-radius: 999px; font-size: 9pt; }
    .transcript { break-before: page; }
    .transcript article { break-inside: avoid; margin-bottom: 16px; padding-left: 12px; border-left: 2px solid #ded6ca; }
    footer { margin-top: 32px; padding-top: 12px; border-top: 1px solid #cfc6b8; color: #766d62; font-size: 8.5pt; }
  </style></head><body><header><h1>${escapeHtml(note.title)}</h1><p>${escapeHtml(noteDate(note))} · 与 ${escapeHtml(note.personaName)} 的心语札记</p></header><main>${blocksToHtml(note.body)}${themes}${sources}${transcript}</main><footer>本札记由真实对话内容整理，并经用户编辑确认；人物回答基于公开资料与模型生成。</footer></body></html>`;
}

export function printNotePdf(bundle: NoteExportBundle, target: Window) {
  target.document.open();
  target.document.write(buildNotePrintHtml(bundle));
  target.document.close();
  target.opener = null;
  window.setTimeout(() => { target.focus(); target.print(); }, 250);
}
