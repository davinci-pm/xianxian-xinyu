"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import CharacterArt from "@/components/character-art";
import { ArrowRightIcon, BookIcon, SearchIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { getNote, listNotes, noteFromConversation, saveNote, subscribeNotes, type NoteRecord } from "@/lib/local-data";
import { downloadNoteDocx, downloadNoteMarkdown, printNotePdf, type NoteExportFormat } from "@/lib/note-export";

export default function NotesClient({ noteId, conversationId }: { noteId?: string; conversationId?: string }) {
  const router = useRouter();
  const [notes, setNotes] = useState<NoteRecord[]>([]);
  const [active, setActive] = useState<NoteRecord | null>(null);
  const [search, setSearch] = useState("");
  const [saveState, setSaveState] = useState<"saved" | "saving" | "offline">("saved");
  const [exportOpen, setExportOpen] = useState(false);
  const [includeTranscript, setIncludeTranscript] = useState(false);
  const [exporting, setExporting] = useState<NoteExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const refresh = () => setNotes(listNotes());
    refresh();
    return subscribeNotes(refresh);
  }, []);

  useEffect(() => {
    if (conversationId) {
      api.conversation(conversationId).then((conversation) => {
        const note = noteFromConversation(conversation); setActive(note); setNotes(listNotes()); router.replace(`/notes/${note.id}`);
      }).catch(() => setError("无法从这段对话生成札记，请先确认会话仍可访问。"));
      return;
    }
    const timer = window.setTimeout(() => setActive(noteId ? getNote(noteId) : listNotes()[0] ?? null), 0);
    return () => window.clearTimeout(timer);
  }, [conversationId, noteId, router]);

  useEffect(() => {
    if (!active) return;
    const timer = window.setTimeout(() => {
      const saved = saveNote(active); setActive(saved); setSaveState(navigator.onLine ? "saved" : "offline");
    }, 650);
    return () => window.clearTimeout(timer);
  }, [active?.body, active?.title]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => notes.filter((note) => `${note.title} ${note.personaName} ${note.summary}`.toLowerCase().includes(search.toLowerCase())), [notes, search]);

  async function exportNote(format: NoteExportFormat) {
    if (!active) return;
    const printTarget = format === "pdf" ? window.open("", "_blank", "width=900,height=1100") : null;
    if (format === "pdf" && !printTarget) { setError("浏览器拦截了打印窗口，请允许弹出窗口后重试。"); return; }
    setExporting(format); setError(null);
    try {
      let conversation;
      try { conversation = await api.conversation(active.conversationId); }
      catch { if (includeTranscript) throw new Error("conversation_unavailable"); }
      const bundle = { note: active, conversation, includeTranscript };
      if (format === "markdown") downloadNoteMarkdown(bundle);
      if (format === "docx") await downloadNoteDocx(bundle);
      if (format === "pdf" && printTarget) printNotePdf(bundle, printTarget);
      setExportOpen(false);
    } catch {
      printTarget?.close();
      setError(includeTranscript ? "无法读取完整对话，请确认网络正常后再试。" : "导出失败，请稍后再试。");
    } finally { setExporting(null); }
  }

  return (
    <main className="notes-page" id="main-content">
      <aside className="notes-sidebar">
        <header><div><p className="eyebrow"><span /> 心语札记</p><h1>留住自己的判断</h1></div><span>{notes.length}</span></header>
        <label className="notes-search"><SearchIcon size={17} /><span className="sr-only">搜索札记</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索人物或札记内容" /></label>
        <div className="notes-list">
          {filtered.map((note) => <Link href={`/notes/${note.id}`} className={active?.id === note.id ? "active" : ""} key={note.id} onClick={() => setActive(note)}><span>{note.personaName.slice(0, 1)}</span><div><strong>{note.title}</strong><p>{note.summary}</p><small>{new Date(note.updatedAt).toLocaleDateString("zh-CN")}</small></div></Link>)}
          {filtered.length === 0 && <div className="notes-list-empty">{notes.length ? "没有符合的札记" : "完成一次对话后，札记会留在这里。"}</div>}
        </div>
      </aside>

      <section className="note-editor">
        {error && <div className="status-banner status-error">{error}</div>}
        {active ? <>
          <header className="note-editor-header"><div><span className={`save-state ${saveState}`}>{saveState === "saving" ? "正在保存…" : saveState === "offline" ? "离线草稿已存本机" : "已自动保存"}</span><small>仅保存在此浏览器</small></div><div><div className="note-export"><button type="button" aria-expanded={exportOpen} onClick={() => setExportOpen((value) => !value)}>导出札记</button>{exportOpen && <div className="note-export-menu"><header><strong>导出心语札记</strong><small>默认只保留重要内容</small></header><div className="note-export-formats"><button type="button" disabled={Boolean(exporting)} onClick={() => exportNote("markdown")}><b>Markdown</b><span>适合知识库</span></button><button type="button" disabled={Boolean(exporting)} onClick={() => exportNote("docx")}><b>Word</b><span>可继续编辑</span></button><button type="button" disabled={Boolean(exporting)} onClick={() => exportNote("pdf")}><b>PDF</b><span>打印或收藏</span></button></div><label><input type="checkbox" checked={includeTranscript} onChange={(event) => setIncludeTranscript(event.target.checked)} /><span><b>附上完整对话记录</b><small>非主要内容，将作为文末附录</small></span></label>{exporting && <p>正在准备{exporting === "docx" ? " Word" : exporting === "pdf" ? " PDF" : " Markdown"}…</p>}</div>}</div><Link href={`/chat/${active.conversationId}`}>继续对话 <ArrowRightIcon size={16} /></Link></div></header>
          <article className="note-paper">
            <p className="note-date">{new Date(active.createdAt).toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" })} · 与 {active.personaName} 的对话</p>
            <label htmlFor="note-title" className="sr-only">札记标题</label><input id="note-title" className="note-title-input" value={active.title} onChange={(event) => { setSaveState(navigator.onLine ? "saving" : "offline"); setActive({ ...active, title: event.target.value }); }} maxLength={120} />
            <div className="note-rule"><span /></div>
            <label htmlFor="note-body" className="sr-only">札记正文</label><textarea id="note-body" value={active.body} onChange={(event) => { setSaveState(navigator.onLine ? "saving" : "offline"); setActive({ ...active, body: event.target.value }); }} aria-describedby="note-help" /><p id="note-help">支持 Markdown 标题与列表。输入停止 650ms 后自动保存。</p>
          </article>
        </> : <div className="note-empty"><BookIcon size={40} /><h2>一段谈话，一页属于你的判断</h2><p>从人物详情开始一段对话，结束后即可生成可编辑的心语札记。</p><Link className="button button-primary" href="/">寻找思想同行者 <ArrowRightIcon /></Link></div>}
      </section>

      <aside className="note-context">
        {active ? <>
          <section><p className="eyebrow"><span /> 对话者</p><CharacterArt slug={active.personaSlug} name={active.personaName} variant="mini" /><h2>{active.personaName}</h2><Link href={`/figures/${active.personaSlug}`}>查看人物资料 <ArrowRightIcon size={15} /></Link></section>
          <section><small>本轮主题</small><div className="note-themes">{active.themes.map((theme) => <span key={theme}>{theme}</span>)}</div></section>
          <section><small>对话中使用的记忆</small>{active.memories.length ? <ul>{active.memories.map((memory) => <li key={memory}>{memory}</li>)}</ul> : <p>这段对话没有使用长期记忆。</p>}</section>
          <div className="note-ai-boundary"><SparkIcon size={18} /><p>札记由真实会话内容整理，仍需由你编辑确认。它不是人物本人的原文。</p></div>
        </> : <div className="note-context-empty"><SparkIcon size={26} /><p>你的主题和经确认记忆会在这里集中展示。</p></div>}
      </aside>
    </main>
  );
}
