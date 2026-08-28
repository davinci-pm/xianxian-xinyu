export const featuredPortraits: Record<string, string> = {
  "andrej-karpathy": "/characters/andrej-karpathy/portrait.webp",
  "charlie-munger": "/characters/charlie-munger/portrait.webp",
  confucius: "/characters/confucius/portrait.webp",
  "elon-musk": "/characters/elon-musk/portrait.webp",
  "fengge-wangmingtianya": "/characters/fengge-wangmingtianya/portrait.webp",
  "ilya-sutskever": "/characters/ilya-sutskever/portrait.webp",
  "mao-zedong": "/characters/mao-zedong/portrait.webp",
  "marcus-aurelius": "/characters/marcus-aurelius/portrait.webp",
  mrbeast: "/characters/mrbeast/portrait.webp",
  "nassim-taleb": "/characters/nassim-taleb/portrait.webp",
  "naval-ravikant": "/characters/naval-ravikant/portrait.webp",
  "new-youth-method": "/characters/new-youth-method/portrait.webp",
  nietzsche: "/characters/nietzsche/portrait.webp",
  "paul-graham": "/characters/paul-graham/portrait.webp",
  "richard-feynman": "/characters/richard-feynman/portrait.webp",
  "selected-works-of-mao": "/characters/selected-works-of-mao/portrait.webp",
  "steve-jobs": "/characters/steve-jobs/portrait.webp",
  "zhang-xuefeng": "/characters/zhang-xuefeng/portrait.webp",
  "zhang-yiming": "/characters/zhang-yiming/portrait.webp",
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
