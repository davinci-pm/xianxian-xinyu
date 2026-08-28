export interface ChatKeyEvent {
  key: string;
  shiftKey: boolean;
  isComposing?: boolean;
  keyCode?: number;
}

export function shouldSendOnEnter(event: ChatKeyEvent) {
  return event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
}

export const dialogueStages = [
  { key: "BREAK_ICE", label: "破冰", note: "建立安全感" },
  { key: "IDENTIFY_PROBLEM", label: "识别问题", note: "看见真正困惑" },
  { key: "CLARIFY", label: "澄清", note: "分清事实与判断" },
  { key: "GUIDANCE", label: "思想引导", note: "换一种看法" },
  { key: "REFLECTION", label: "反思", note: "形成你的判断" },
  { key: "END", label: "收束", note: "带走一个行动" },
] as const;

export function stageIndex(stage: string) {
  const found = dialogueStages.findIndex((item) => item.key === stage);
  return found < 0 ? 0 : found;
}

export function stageLabel(stage: string) {
  if (stage === "SAFETY") return "安全支持";
  return dialogueStages.find((item) => item.key === stage)?.label ?? stage;
}

export function appendOptimistic<T>(current: T[], user: T, placeholder: T, isRetry: boolean) {
  return isRetry ? [...current, placeholder] : [...current, user, placeholder];
}
