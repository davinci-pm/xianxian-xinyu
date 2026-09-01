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
  event: "meta" | "heartbeat" | "retry" | "chunk" | "degraded" | "done" | "error";
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

export type PersonaTargetType =
  | "self"
  | "authorized_private"
  | "public_figure"
  | "deceased"
  | "composite"
  | "fictional";

export interface StudioSource {
  id: string;
  filename: string;
  source_type: string;
  mime_type: string;
  char_count: number;
  target_speaker: string | null;
  time_range: string | null;
  source_url: string | null;
  published_at: string | null;
  rights_confirmed: boolean;
  status: string;
  created_at: string;
}

export interface StudioClaim {
  id: string;
  claim_type: string;
  content: string;
  confidence: number;
  review_status: string;
  evidence_count: number;
}

export interface StudioProject {
  id: string;
  name: string;
  target_type: PersonaTargetType;
  relationship: string;
  purpose: string;
  language: string;
  visibility: string;
  status: string;
  source_char_count: number;
  quality_score: number;
  persona_slug: string | null;
  sources: StudioSource[];
  claims: StudioClaim[];
  created_at: string;
  updated_at: string;
}

export interface StudioDistillationResult {
  project: StudioProject;
  persona: PersonaCard;
  version: string;
  job_id: string;
  quality_score: number;
  pipeline: StudioPipelineReport;
}

export interface StudioPipelineStage {
  key: string;
  label: string;
  status: string;
  count: number;
  detail: string;
}

export interface StudioPipelineReport {
  pipeline_version: string;
  stages: StudioPipelineStage[];
  evaluation: {
    score: number;
    dimensions: Record<string, number>;
    case_count: number;
  };
  artifact_counts: Record<string, number>;
}

export interface StudioPipelineStatus {
  pipeline_version: string;
  job_id: string | null;
  status: string;
  progress: number;
  stages: StudioPipelineStage[];
  evaluation_score: number | null;
  evaluation_dimensions: Record<string, number>;
  artifact_counts: Record<string, number>;
  pending_feedback: number;
}

export interface StudioFeedback {
  id: string;
  feedback_type: "fact_error" | "unlike" | "missing_context" | "better_response";
  content: string;
  target_artifact_id: string | null;
  status: string;
  review_note: string | null;
  created_at: string;
}

export interface StudioHealthDimension {
  key: string;
  label: string;
  score: number;
  status: "strong" | "usable" | "gap";
  detail: string;
}

export interface StudioHealthReport {
  readiness_level: "轮廓版" | "可用版" | "推荐版" | "高保真版";
  overall_score: number;
  effective_chars: number;
  substantive_utterances: number;
  decision_signals: number;
  domains_covered: string[];
  source_types: string[];
  adaptive_tier: "outline" | "structured" | "deep" | "trainable";
  enabled_capabilities: string[];
  fidelity_validated: boolean;
  metric_scope: string;
  data_profile: {
    chat_target_turns: number;
    chat_sessions: number;
    contextual_target_turns: number;
    temporal_span_days: number;
    holdout_ready: boolean;
  };
  dimensions: StudioHealthDimension[];
  gaps: string[];
  recommended_questions: string[];
  can_distill: boolean;
}

export interface OwnedPersona extends PersonaCard {
  version: string;
  quality_score: number;
  visibility: string;
  project_id: string | null;
}
