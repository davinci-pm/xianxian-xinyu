"use client";

import { useEffect, useMemo, useState } from "react";
import { MemoryIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { applyMemoryOverlay, getMemoryOverlays, saveMemoryOverlay, type MemoryOverlay } from "@/lib/local-data";
import type { MemoryItem, SessionInfo } from "@/lib/types";

type DisplayMemory = MemoryItem & { hidden: boolean; paused: boolean };

function kindLabel(kind: string) {
  return ({ preference: "你的偏好", unresolved_issue: "尚未解决的问题", personal_context: "个人背景", goal: "你在意的目标" } as Record<string, string>)[kind] ?? "对话记忆";
}

export default function MemorySettingsClient() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [overlays, setOverlays] = useState<MemoryOverlay[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.session(), api.memories()]).then(([sessionData, memoryData]) => { setSession(sessionData); setMemories(memoryData); setOverlays(getMemoryOverlays()); }).catch(() => setError("无法读取记忆，请确认本地服务已经启动。"));
  }, []);

  const displayed = useMemo(() => memories.map((memory) => applyMemoryOverlay(memory, overlays) as DisplayMemory).filter((memory) => showHidden || !memory.hidden), [memories, overlays, showHidden]);

  function update(overlay: MemoryOverlay) { setOverlays(saveMemoryOverlay(overlay)); }
  function startEdit(memory: DisplayMemory) { setEditing(memory.id); setDraft(memory.content); }
  function saveEdit(memory: DisplayMemory) { if (draft.trim()) update({ memoryId: memory.id, content: draft.trim() }); setEditing(null); }

  return (
    <main className="memory-page page-shell" id="main-content">
      <header className="memory-page-header"><div><p className="eyebrow"><span /> 记忆设置</p><h1>你决定什么值得被记住。</h1><p>长期记忆只保存你明确确认的内容。你可以暂停使用、修改本机展示或隐藏记录。</p></div><MemoryIcon size={52} /></header>

      <div className="memory-boundary"><SparkIcon /><div><strong>{session?.authenticated ? "账号长期记忆可用" : "当前为游客模式"}</strong><p>{session?.authenticated ? "经确认记忆可跨会话使用。" : "后端会用浏览器访客身份恢复已确认内容；换浏览器或清理 Cookie 后无法保证恢复。"}</p></div></div>
      <div className="local-overlay-notice"><strong>关于“修改”和“隐藏”</strong><p>当前后端尚未提供记忆编辑/删除接口，所以这些操作只影响此浏览器的前端展示，不会伪称已从服务器删除。暂停会在本机标记为不应展示。</p></div>
      {error && <div className="status-banner status-error">{error}</div>}

      <section className="memory-list-section">
        <header><div><h2>已确认的记忆</h2><p>{memories.length} 条由你主动确认</p></div>{memories.some((memory) => applyMemoryOverlay(memory, overlays).hidden) && <button type="button" onClick={() => setShowHidden((value) => !value)}>{showHidden ? "隐藏已移除记录" : "查看已隐藏记录"}</button>}</header>
        <div className="memory-settings-list">
          {displayed.map((memory) => <article className={`${memory.paused ? "paused" : ""} ${memory.hidden ? "hidden" : ""}`} key={memory.id}>
            <div className="memory-kind"><span>{kindLabel(memory.kind)}</span><small>置信度 {memory.confidence}%</small></div>
            {editing === memory.id ? <div className="memory-edit"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={3} maxLength={500} autoFocus /><div><button type="button" onClick={() => setEditing(null)}>取消</button><button type="button" onClick={() => saveEdit(memory)}>保存本机展示</button></div></div> : <p>{memory.content}</p>}
            <footer><span>{new Date(memory.created_at).toLocaleDateString("zh-CN")}{memory.paused && " · 已暂停"}{memory.hidden && " · 已隐藏"}</span><div><button type="button" onClick={() => update({ memoryId: memory.id, paused: !memory.paused })}>{memory.paused ? "恢复使用" : "暂停使用"}</button><button type="button" onClick={() => startEdit(memory)}>修改展示</button><button className="danger" type="button" onClick={() => update({ memoryId: memory.id, hidden: !memory.hidden })}>{memory.hidden ? "恢复显示" : "从本机隐藏"}</button></div></footer>
          </article>)}
          {!error && displayed.length === 0 && <div className="memory-empty"><MemoryIcon size={36} /><h2>{memories.length ? "当前记录已全部隐藏" : "还没有经你确认的记忆"}</h2><p>当对话中出现可能有助于下次继续的内容，我们会先询问你，绝不会静默保存。</p></div>}
        </div>
      </section>
    </main>
  );
}

