import { readSse } from "@/lib/sse";
import type {
  ConversationCreateResponse,
  ConversationDetail,
  ConversationSummary,
  MemoryItem,
  PersonaCard,
  PersonaDetail,
  StreamEvent,
  SessionInfo,
  SkillInfo,
} from "@/lib/types";

const BASE = "/api/backend";

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`API ${response.status}`);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  session: () => jsonRequest<SessionInfo>("/session"),
  login: (inviteCode: string) =>
    jsonRequest<SessionInfo>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ invite_code: inviteCode }),
    }),
  logout: () => jsonRequest<void>("/auth/logout", { method: "POST" }),
  personas: () => jsonRequest<PersonaCard[]>("/personas"),
  persona: (slug: string) => jsonRequest<PersonaDetail>(`/personas/${slug}`),
  conversations: () => jsonRequest<ConversationSummary[]>("/conversations"),
  conversation: (id: string) => jsonRequest<ConversationDetail>(`/conversations/${id}`),
  createConversation: (personaSlug: string) =>
    jsonRequest<ConversationCreateResponse>("/conversations", {
      method: "POST",
      body: JSON.stringify({ persona_slug: personaSlug }),
    }),
  confirmMemory: (id: string, action: "remember" | "session_only" | "discard") =>
    jsonRequest<MemoryItem>(`/memories/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  memories: () => jsonRequest<MemoryItem[]>("/memories"),
  updateMemory: (id: string, payload: { content?: string; paused?: boolean }) =>
    jsonRequest<MemoryItem>(`/memories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteMemory: (id: string) =>
    jsonRequest<void>(`/memories/${id}`, { method: "DELETE" }),
  skills: () => jsonRequest<SkillInfo[]>("/skills"),
  async *sendMessage(
    conversationId: string,
    content: string,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): AsyncGenerator<StreamEvent> {
    const response = await fetch(`${BASE}/conversations/${conversationId}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ content, idempotency_key: idempotencyKey }),
      signal,
    });
    yield* readSse(response);
  },
};
