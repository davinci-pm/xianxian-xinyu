"use client";

import { useEffect, useState } from "react";
import { MemoryIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import type { MemoryItem, SessionInfo } from "@/lib/types";

function kindLabel(kind: string) {
  return ({ preference: "你的偏好", unresolved_issue: "尚未解决的问题", personal_context: "个人背景", goal: "你在意的目标", decision: "你做出的决定" } as Record<string, string>)[kind] ?? "对话记忆";
}

export default function MemorySettingsClient() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.session(), api.memories()]).then(([sessionData, memoryData]) => { setSession(sessionData); setMemories(memoryData); }).catch(() => setError("无法读取记忆，请稍后再试。"));
  }, []);

  function startEdit(memory: MemoryItem) { setEditing(memory.id); setDraft(memory.content); }
  async function saveEdit(memory: MemoryItem) {
    if (!draft.trim()) return;
    setBusyId(memory.id); setError(null);
    try {
      const updated = await api.updateMemory(memory.id, { content: draft.trim() });
      setMemories((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEditing(null);
    } catch { setError("记忆修改失败，请稍后再试。"); }
    finally { setBusyId(null); }
  }
  async function togglePause(memory: MemoryItem) {
    setBusyId(memory.id); setError(null);
    try {
      const updated = await api.updateMemory(memory.id, { paused: memory.status !== "paused" });
      setMemories((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch { setError("记忆状态修改失败，请稍后再试。"); }
    finally { setBusyId(null); }
  }
  async function remove(memory: MemoryItem) {
    if (!window.confirm("永久删除这条记忆？删除后，这位人物将不再使用它。")) return;
    setBusyId(memory.id); setError(null);
    try {
      await api.deleteMemory(memory.id);
      setMemories((current) => current.filter((item) => item.id !== memory.id));
    } catch { setError("记忆删除失败，请稍后再试。"); }
    finally { setBusyId(null); }
  }

  return (
    <main className="memory-page page-shell" id="main-content">
      <header className="memory-page-header"><div><p className="eyebrow"><span /> 记忆设置</p><h1>你决定什么值得被记住。</h1><p>系统只会为重要且可能长期有效的信息征求确认。你可以随时修改、暂停或永久删除。</p></div><MemoryIcon size={52} /></header>

      <div className="memory-boundary"><SparkIcon /><div><strong>{session?.authenticated ? "账号长期记忆可用" : "当前为游客模式"}</strong><p>{session?.authenticated ? "经确认记忆可跨会话使用。" : "后端会用浏览器访客身份恢复已确认内容；换浏览器或清理 Cookie 后无法保证恢复。"}</p></div></div>
      {error && <div className="status-banner status-error">{error}</div>}

      <section className="memory-list-section">
        <header><div><h2>已确认的记忆</h2><p>{memories.length} 条由你主动确认，仅属于对应人物</p></div></header>
        <div className="memory-settings-list">
          {memories.map((memory) => <article className={memory.status === "paused" ? "paused" : ""} key={memory.id}>
            <div className="memory-kind"><span>{kindLabel(memory.kind)}</span><small>置信度 {memory.confidence}%</small></div>
            {editing === memory.id ? <div className="memory-edit"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={3} maxLength={500} autoFocus /><div><button type="button" disabled={busyId === memory.id} onClick={() => setEditing(null)}>取消</button><button type="button" disabled={busyId === memory.id} onClick={() => saveEdit(memory)}>{busyId === memory.id ? "保存中…" : "保存修改"}</button></div></div> : <p>{memory.content}</p>}
            <footer><span>{new Date(memory.created_at).toLocaleDateString("zh-CN")}{memory.status === "paused" && " · 已暂停使用"}</span><div><button type="button" disabled={busyId === memory.id} onClick={() => togglePause(memory)}>{memory.status === "paused" ? "恢复使用" : "暂停使用"}</button><button type="button" disabled={busyId === memory.id} onClick={() => startEdit(memory)}>修改</button><button className="danger" type="button" disabled={busyId === memory.id} onClick={() => remove(memory)}>永久删除</button></div></footer>
          </article>)}
          {!error && memories.length === 0 && <div className="memory-empty"><MemoryIcon size={36} /><h2>还没有经你确认的记忆</h2><p>当对话中出现重要且可能长期有效的信息时，这位人物会先询问你。</p></div>}
        </div>
      </section>
    </main>
  );
}
