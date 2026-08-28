export const featuredPortraits: Record<string, string> = {
  confucius: "/characters/confucius/portrait.webp",
  nietzsche: "/characters/nietzsche/portrait.webp",
  "marcus-aurelius": "/characters/marcus-aurelius/portrait.webp",
};

export const personaQuotes: Record<string, string> = {
  confucius: "先从你所处的关系里，看清此刻真正要承担的那一步。",
  nietzsche: "别急着摆脱痛苦，先看看它正在逼你成为什么样的人。",
  "marcus-aurelius": "分清什么由你掌控，然后把心力放回可以行动之处。",
};

export const personaMarks: Record<string, string> = {
  confucius: "仁",
  nietzsche: "火",
  "marcus-aurelius": "静",
};

export function displayPersonaName(name: string) {
  return name.replace(/视角$|方法$/, "").trim();
}

