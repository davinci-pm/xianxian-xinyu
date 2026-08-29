"use client";

import Link from "next/link";
import { FormEvent, Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import CharacterArt from "@/components/character-art";
import Drawer from "@/components/drawer";
import QuickReplies from "@/components/quick-replies";
import { ArrowRightIcon, BookIcon, ExternalIcon, MemoryIcon, MoreIcon, QuoteIcon, SendIcon, StopIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { appendOptimistic, dialogueStages, shouldSendOnEnter, stageIndex, stageLabel } from "@/lib/chat-utils";
import { displayPersonaName } from "@/lib/persona-visual";
import type { ChatMessage, Citation, ConversationDetail, MemoryItem } from "@/lib/types";

type LocalMessage = ChatMessage & { localStatus?: "streaming" | "stopped" };
type DrawerKind = "sources" | "memory" | null;

function InlineText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return <>{parts.map((part, index) => part.startsWith("**") && part.endsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong> : <Fragment key={index}>{part}</Fragment>)}</>;
}

function RichMessage({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/).filter(Boolean);
  return <div className="rich-message">{blocks.map((block, index) => {
    const lines = block.split("\n");
    if (lines.every((line) => /^[-*]\s+/.test(line))) return <ul key={index}>{lines.map((line, itemIndex) => <li key={itemIndex}><InlineText text={line.replace(/^[-*]\s+/, "")} /></li>)}</ul>;
    if (lines.every((line) => /^\d+[.)]\s+/.test(line))) return <ol key={index}>{lines.map((line, itemIndex) => <li key={itemIndex}><InlineText text={line.replace(/^\d+[.)]\s+/, "")} /></li>)}</ol>;
    return <p key={index}>{lines.map((line, lineIndex) => <Fragment key={lineIndex}><InlineText text={line} />{lineIndex < lines.length - 1 && <br />}</Fragment>)}</p>;
  })}</div>;
}

function memoryKind(kind: string) {
  return ({ preference: "偏好", unresolved_issue: "未解决问题", personal_context: "个人背景", goal: "目标" } as Record<string, string>)[kind] ?? "对话记忆";
}

export default function ChatClient({ conversationId }: { conversationId: string }) {
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [candidates, setCandidates] = useState<MemoryItem[]>([]);
  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerKind>(null);
  const [failed, setFailed] = useState<{ content: string; key: string } | null>(null);
  const [note, setNote] = useState("");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [savingMemoryId, setSavingMemoryId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.conversation(conversationId).then((data) => {
      setConversation(data); setMessages(data.messages); setCandidates(data.memory_candidates);
      const stored = sessionStorage.getItem(`quick-replies:${conversationId}`);
      const pendingConcern = sessionStorage.getItem(`pending-concern:${conversationId}`);
      const base = stored ? JSON.parse(stored) as string[] : [];
      setQuickReplies(pendingConcern ? [pendingConcern, ...base] : base);
      setNote(data.unresolved_issue ?? "");
    }).catch(() => setError("无法读取这段对话。它可能属于另一个浏览器会话。"));
  }, [conversationId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: streaming ? "auto" : "smooth" }); }, [messages, streaming]);

  const allCitations = useMemo(() => {
    const seen = new Set<string>();
    return messages.flatMap((message) => message.citations ?? []).filter((citation) => {
      const key = `${citation.document_id}:${citation.label}`;
      if (seen.has(key)) return false; seen.add(key); return true;
    });
  }, [messages]);

  const send = useCallback(async (content: string, retry?: { key: string }) => {
    const clean = content.trim();
    if (!clean || streaming || !conversation) return;
    setInput(""); setQuickReplies([]); setStreaming(true); setDegraded(false); setError(null); setFailed(null);
    const idempotencyKey = retry?.key ?? crypto.randomUUID();
    const optimisticUser: LocalMessage = { id: `local-user-${idempotencyKey}`, role: "user", content: clean, stage: conversation.stage, citations: [], degraded: false, created_at: new Date().toISOString() };
    const placeholderId = `stream-${idempotencyKey}`;
    const placeholder: LocalMessage = { id: placeholderId, role: "assistant", content: "", stage: conversation.stage, citations: [], degraded: false, created_at: new Date().toISOString(), localStatus: "streaming" };
    setMessages((current) => appendOptimistic(current, optimisticUser, placeholder, Boolean(retry)));
    const controller = new AbortController(); abortRef.current = controller;
    try {
      for await (const event of api.sendMessage(conversationId, clean, idempotencyKey, controller.signal)) {
        if (event.event === "meta") {
          const candidate = event.data.memory_candidate as MemoryItem | null | undefined;
          if (candidate) setCandidates((current) => current.some((item) => item.id === candidate.id) ? current : [candidate, ...current]);
          const stage = event.data.stage;
          if (typeof stage === "string") setConversation((current) => current ? { ...current, stage } : current);
        }
        if (event.event === "chunk") {
          const text = typeof event.data.text === "string" ? event.data.text : "";
          setMessages((current) => current.map((message) => message.id === placeholderId ? { ...message, content: message.content + text } : message));
        }
        if (event.event === "degraded") setDegraded(true);
        if (event.event === "done") {
          const saved = event.data.message as ChatMessage;
          setMessages((current) => current.map((message) => message.id === placeholderId ? saved : message));
          const stage = event.data.conversation_stage;
          if (typeof stage === "string") setConversation((current) => current ? { ...current, stage } : current);
        }
      }
    } catch {
      if (controller.signal.aborted) {
        setMessages((current) => current.map((message) => message.id === placeholderId ? { ...message, localStatus: "stopped", content: message.content || "已停止本轮生成。" } : message));
      } else {
        setError("这轮对话没有完整送达。可以使用同一请求安全重试，不会重复提交你的输入。");
        setFailed({ content: clean, key: idempotencyKey });
        setMessages((current) => current.filter((message) => message.id !== placeholderId));
      }
    } finally { abortRef.current = null; setStreaming(false); }
  }, [conversation, conversationId, streaming]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); await send(input); }
  function chooseQuickReply(reply: string) { setInput(reply); requestAnimationFrame(() => textareaRef.current?.focus()); }
  async function decideMemory(memory: MemoryItem, action: "remember" | "session_only" | "discard") {
    if (streaming || savingMemoryId) return;
    setSavingMemoryId(memory.id);
    setError(null);
    try {
      const updated = await api.confirmMemory(memory.id, action);
      setCandidates((current) => current.filter((item) => item.id !== memory.id));
      if (action === "remember") setConversation((current) => current ? { ...current, confirmed_memories: [updated, ...current.confirmed_memories.filter((item) => item.id !== updated.id)] } : current);
    } catch { setError("记忆选择未保存，请再试一次。"); }
    finally { setSavingMemoryId(null); }
  }

  if (!conversation) return <main className="chat-loading" id="main-content"><div className="thinking-orbit" />{error ?? "正在恢复对话与记忆…"}</main>;
  const name = displayPersonaName(conversation.persona.name_zh);
  const currentStageIndex = stageIndex(conversation.stage);

  return (
    <main className="chat-layout-redesign" id="main-content">
      <header className="chat-mobile-header">
        <Link href={`/figures/${conversation.persona.slug}`} aria-label={`查看${name}人物资料`}><CharacterArt slug={conversation.persona.slug} name={conversation.persona.name_zh} variant="avatar" /></Link>
        <div><strong>{name}</strong><small>{stageLabel(conversation.stage)}</small></div>
        <button type="button" aria-label="打开对话菜单" onClick={() => setMobileMenu((value) => !value)}><MoreIcon /></button>
        {mobileMenu && <div className="chat-mobile-menu"><button type="button" onClick={() => { setDrawer("sources"); setMobileMenu(false); }}>查看引用</button><button type="button" onClick={() => { setDrawer("memory"); setMobileMenu(false); }}>查看记忆</button><Link href="/notes">心语札记</Link></div>}
      </header>

      <aside className="chat-left">
        <Link href={`/figures/${conversation.persona.slug}`} className="chat-back">← 人物资料</Link>
        <CharacterArt slug={conversation.persona.slug} name={conversation.persona.name_zh} variant="avatar" />
        <p className="eyebrow"><span /> 当前对话者</p><h1>{name}</h1><p className="chat-persona-intro">{conversation.persona.short_intro}</p>
        <div className="chat-stage-list"><small>对话进程</small><ol>{dialogueStages.map((stage, index) => <li className={index === currentStageIndex ? "active" : index < currentStageIndex ? "done" : ""} key={stage.key}><span>{index < currentStageIndex ? "✓" : index + 1}</span><div><b>{stage.label}</b><small>{stage.note}</small></div></li>)}</ol></div>
        <p className="persona-boundary">思想对话基于公开资料与作品构建<br />重要判断请回到原始资料</p>
      </aside>

      <section className="chat-center">
        {conversation.persona.is_living && <div className="chat-disclaimer living">在世人物思想对话 · 基于公开资料 · 非本人授权或实时观点</div>}
        <div className="chat-mobile-progress"><span style={{ width: `${((currentStageIndex + 1) / dialogueStages.length) * 100}%` }} /><b>{stageLabel(conversation.stage)}</b><small>{currentStageIndex + 1}/{dialogueStages.length}</small></div>
        <div className="message-list-redesign" aria-live="polite" aria-busy={streaming}>
          <div className="conversation-date"><span>这段对话</span></div>
          {messages.map((message) => (
            <article className={`message-card ${message.role}`} key={message.id}>
              <div className="message-avatar">{message.role === "assistant" ? <CharacterArt slug={conversation.persona.slug} name={conversation.persona.name_zh} variant="avatar" /> : <span>你</span>}</div>
              <div className="message-content">
                <header><strong>{message.role === "assistant" ? name : "你"}</strong>{message.stage && <span>{stageLabel(message.stage)}</span>}</header>
                <div className="message-paper">{message.content ? <RichMessage content={message.content} /> : <span className="thinking"><i /><i /><i /> 正在思量你的话…</span>}{message.localStatus === "stopped" && <small className="message-status">本轮已停止</small>}{message.degraded && <small className="degraded-note">本轮真实生成未完整返回，已使用人物风格保底回复</small>}</div>
                {message.citations?.length > 0 && <button className="message-citation-button" type="button" onClick={() => setDrawer("sources")}><BookIcon size={15} /> 本段参考 {message.citations.length} 条公开资料 <ArrowRightIcon size={14} /></button>}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="chat-action-zone">
          {candidates.map((memory) => <div className="memory-prompt" key={memory.id} data-testid="memory-candidate"><MemoryIcon /><div><small>这件事可能会影响以后的对话，要让我记住吗？</small><p>{memory.content}</p></div><div><button type="button" disabled={streaming || savingMemoryId === memory.id} onClick={() => decideMemory(memory, "remember")}>{savingMemoryId === memory.id ? "保存中…" : "记住"}</button><button type="button" disabled={streaming || savingMemoryId === memory.id} onClick={() => decideMemory(memory, "session_only")}>仅本次</button><button type="button" disabled={streaming || savingMemoryId === memory.id} onClick={() => decideMemory(memory, "discard")}>不保存</button></div></div>)}
          {conversation.stage === "SAFETY" && <div className="safety-recovery" data-testid="safety-recovery-panel" role="status"><div><strong>安全支持已开启，但输入不会被锁定</strong><p>人物角色已暂停。你可以继续自由输入，或告诉我你当前的安全状况。</p></div><div><button type="button" onClick={() => send("我现在安全")} disabled={streaming}>我现在安全</button><button type="button" className="urgent" onClick={() => send("我有立即行动的打算")} disabled={streaming}>我需要紧急帮助</button></div></div>}
          {degraded && <div className="degraded-banner">本轮真实生成未完整返回，已使用人物风格保底回复。</div>}
          {error && <div className="status-banner status-error" role="alert">{error}{failed && <button type="button" onClick={() => send(failed.content, { key: failed.key })}>安全重试</button>}</div>}
          <QuickReplies replies={quickReplies} onChoose={chooseQuickReply} />
          <form className="composer-redesign" onSubmit={handleSubmit}>
            <label htmlFor="message-input" className="sr-only">{conversation.stage === "SAFETY" ? "安全支持中，你仍可以自由输入" : "你也可以自由输入"}</label>
            <textarea ref={textareaRef} id="message-input" value={input} onChange={(event) => setInput(event.target.value)} placeholder={conversation.stage === "SAFETY" ? "你可以回复‘我现在安全’，或继续告诉我此刻的状况…" : "不必组织得很完整，从眼下最难说清的那一点开始…"} rows={2} maxLength={4000} onKeyDown={(event) => { if (shouldSendOnEnter({ key: event.key, shiftKey: event.shiftKey, isComposing: event.nativeEvent.isComposing, keyCode: event.keyCode })) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} />
            <div className="composer-actions"><span>{input.length > 3600 ? `${input.length}/4000` : "Enter 发送 · Shift + Enter 换行"}</span>{streaming ? <button type="button" className="stop-button" onClick={() => abortRef.current?.abort()}><StopIcon size={16} /> 停止</button> : <button type="submit" disabled={!input.trim()} aria-label="发送消息"><SendIcon /></button>}</div>
          </form>
          <p className="composer-notice">重要判断请结合原始资料与现实处境。</p>
        </div>
      </section>

      <aside className="chat-right">
        <section><header><div><small>本轮线索</small><h2>正在谈什么</h2></div><QuoteIcon /></header><textarea aria-label="记录本轮线索" value={note} onChange={(event) => setNote(event.target.value)} placeholder="尚未形成清晰线索…" rows={4} /><small>仅保存在当前页面，Phase 4 将写入札记。</small></section>
        <section><header><div><small>公开资料</small><h2>本轮引用</h2></div><button type="button" onClick={() => setDrawer("sources")} aria-label="打开全部引用"><ArrowRightIcon /></button></header>{allCitations.length ? <ul className="context-list">{allCitations.slice(0, 3).map((citation) => <li key={`${citation.document_id}-${citation.label}`}><BookIcon /><span>{citation.label}</span></li>)}</ul> : <p className="context-empty">对话引用会在这里出现。你可以随时查看它们来自哪里。</p>}</section>
        <section><header><div><small>经你确认</small><h2>记忆上下文</h2></div><button type="button" onClick={() => setDrawer("memory")} aria-label="打开全部记忆"><ArrowRightIcon /></button></header>{conversation.confirmed_memories.length ? <ul className="context-list" data-testid="remembered-context">{conversation.confirmed_memories.slice(0, 3).map((memory) => <li key={memory.id}><MemoryIcon /><span>{memory.content}</span></li>)}</ul> : <p className="context-empty">只有你明确确认后，内容才会进入长期记忆。</p>}</section>
        <Link className="end-conversation" href={`/notes?conversation=${conversation.id}`}>结束并生成心语札记 <ArrowRightIcon /></Link>
      </aside>

      <Drawer open={drawer === "sources"} onClose={() => setDrawer(null)} eyebrow="知识依据" title="本轮公开资料">
        {allCitations.length ? <ol className="drawer-source-list">{allCitations.map((citation: Citation, index) => <li key={`${citation.document_id}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{citation.label}</strong>{citation.source_url && <a href={citation.source_url} target="_blank" rel="noreferrer">查看原始来源 <ExternalIcon size={14} /></a>}</div></li>)}</ol> : <div className="drawer-empty"><BookIcon size={30} /><p>这段对话还没有返回可展示的引用。人物资料页仍可查看基础资料来源。</p><Link href={`/figures/${conversation.persona.slug}`}>查看人物资料 <ArrowRightIcon /></Link></div>}
      </Drawer>
      <Drawer open={drawer === "memory"} onClose={() => setDrawer(null)} eyebrow="你拥有控制权" title="这位人物记得什么">
        <p className="drawer-intro">只有你明确点击“记住”的内容才会出现。你可以前往记忆设置暂停、修改展示或隐藏。</p>
        {conversation.confirmed_memories.length ? <ul className="drawer-memory-list">{conversation.confirmed_memories.map((memory) => <li key={memory.id}><span>{memoryKind(memory.kind)}</span><p>{memory.content}</p><small>置信度 {memory.confidence}%</small></li>)}</ul> : <div className="drawer-empty"><MemoryIcon size={30} /><p>当前还没有经你确认的长期记忆。</p></div>}
        <Link className="button button-secondary drawer-settings-link" href="/settings/memory">打开记忆设置 <ArrowRightIcon /></Link>
      </Drawer>
    </main>
  );
}
