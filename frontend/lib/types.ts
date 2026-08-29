export interface PersonaCard {
  id: string;
  slug: string;
  name_zh: string;
  name_en: string;
  era: string;
  region: string;
  domains: string[];
  topics: string[];
  dilemmas: string[];
  short_intro: string;
  avatar_tone: string;
  chat_tier: string;
  chat_enabled: boolean;
  is_living: boolean;
}

export interface SourceItem {
  title: string;
  citation_label: string;
  source_url: string | null;
  license_note: string;
}

export interface PersonaDetail extends PersonaCard {
  identity: Record<string, unknown>;
  principles: Array<Record<string, string>>;
  suitable_questions: string[];
  representative_views: string[];
  quick_replies: string[];
  sources: SourceItem[];
  disclaimer: string;
}

export interface Citation {
  document_id: string;
  label: string;
  source_url: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  stage: string | null;
  citations: Citation[];
  degraded: boolean;
  created_at: string;
}

export interface MemoryItem {
  id: string;
  kind: string;
  content: string;
  scope: string;
  status: string;
  confidence: number;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  persona: PersonaCard;
  title: string;
  stage: string;
  status: string;
  short_summary: string | null;
  unresolved_issue: string | null;
  messages: ChatMessage[];
  memory_candidates: MemoryItem[];
  confirmed_memories: MemoryItem[];
}

export interface ConversationSummary {
  id: string;
  persona_slug: string;
  persona_name: string;
  title: string;
  stage: string;
  status: string;
  short_summary: string | null;
  last_message_at: string;
}

export interface ConversationCreateResponse {
  conversation: ConversationDetail;
  opening_message: ChatMessage;
  quick_replies: string[];
  remembered_context: string[];
}

export interface StreamEvent {
  event: "meta" | "retry" | "chunk" | "degraded" | "done" | "error";
  data: Record<string, unknown>;
}

export interface SessionInfo {
  authenticated: boolean;
  auth_required: boolean;
  locale: string;
  long_memory_available: boolean;
  display_name: string | null;
}

export interface SkillInfo {
  skill_key: string;
  name: string;
  version: string;
  source: string;
  license_name: string;
  risk_level: string;
  permissions: string[];
  allowlisted: boolean;
  enabled: boolean;
}
