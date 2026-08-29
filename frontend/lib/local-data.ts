import type { ConversationDetail } from "@/lib/types";
import { displayPersonaName } from "@/lib/persona-visual";

export interface NoteRecord {
  id: string;
  conversationId: string;
  personaSlug: string;
  personaName: string;
  title: string;
  summary: string;
  body: string;
  themes: string[];
  memories: string[];
  createdAt: string;
  updatedAt: string;
}

const NOTES_KEY = "xianxian-notes-v1";
const NOTES_EVENT = "xianxian:notes-changed";

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try { return JSON.parse(localStorage.getItem(key) ?? "") as T; } catch { return fallback; }
}

function writeJson<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function listNotes() {
  return readJson<NoteRecord[]>(NOTES_KEY, []).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getNote(id: string) {
  return listNotes().find((note) => note.id === id) ?? null;
}

export function saveNote(note: NoteRecord) {
  const notes = listNotes();
  const index = notes.findIndex((item) => item.id === note.id);
  const updated = { ...note, updatedAt: new Date().toISOString() };
  if (index >= 0) notes[index] = updated; else notes.unshift(updated);
  writeJson(NOTES_KEY, notes);
  window.dispatchEvent(new Event(NOTES_EVENT));
  return updated;
}

export function subscribeNotes(listener: () => void) {
  window.addEventListener(NOTES_EVENT, listener);
  window.addEventListener("storage", listener);
  return () => { window.removeEventListener(NOTES_EVENT, listener); window.removeEventListener("storage", listener); };
}

function extractThemes(conversation: ConversationDetail) {
  const text = conversation.messages.map((message) => message.content).join(" ");
  const candidates = [...conversation.persona.topics, ...conversation.persona.dilemmas];
  const matched = candidates.filter((item) => text.includes(item));
  return Array.from(new Set(matched.length ? matched : conversation.persona.topics.slice(0, 3))).slice(0, 5);
}

export function noteFromConversation(conversation: ConversationDetail): NoteRecord {
  const existing = listNotes().find((note) => note.conversationId === conversation.id);
  if (existing) return existing;
  const now = new Date().toISOString();
  const userLines = conversation.messages.filter((message) => message.role === "user").map((message) => message.content);
  const assistantLines = conversation.messages.filter((message) => message.role === "assistant").map((message) => message.content);
  const body = [
    "## 我带来的困惑",
    userLines[0] ?? conversation.unresolved_issue ?? "这段对话刚刚开始，还没有写下具体困惑。",
    "## 对话中被照亮的地方",
    assistantLines.at(-1) ?? "继续对话后，这里会沉淀最重要的一段回应。",
    "## 我想带走的一步",
    "在这里写下一个由你自己决定的、足够小的下一步。",
  ].join("\n\n");
  return saveNote({
    id: crypto.randomUUID(), conversationId: conversation.id, personaSlug: conversation.persona.slug,
    personaName: displayPersonaName(conversation.persona.name_zh), title: `与${displayPersonaName(conversation.persona.name_zh)}谈过之后`,
    summary: conversation.short_summary ?? assistantLines.at(-1)?.slice(0, 120) ?? "一段仍在展开的思想对话",
    body, themes: extractThemes(conversation), memories: conversation.confirmed_memories.map((memory) => memory.content), createdAt: now, updatedAt: now,
  });
}

