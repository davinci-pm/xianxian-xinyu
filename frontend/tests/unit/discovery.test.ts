import { describe, expect, it } from "vitest";
import { emptyDiscoveryFilters, matchesDiscovery } from "@/lib/discovery";
import type { PersonaCard } from "@/lib/types";

const confucius: PersonaCard = {
  id: "1", slug: "confucius", name_zh: "孔子", name_en: "Confucius", era: "春秋时期", region: "中国",
  domains: ["伦理", "教育"], topics: ["人生选择", "人际关系"], dilemmas: ["方向迷茫", "家庭冲突"],
  short_intro: "从关系与责任出发。", avatar_tone: "cinnabar", chat_tier: "A", chat_enabled: true, is_living: false,
};

describe("人物发现筛选", () => {
  it("组合筛选只匹配同时满足的角色", () => {
    expect(matchesDiscovery(confucius, "孔子", { ...emptyDiscoveryFilters, era: "春秋时期", topic: "人际关系" })).toBe(true);
    expect(matchesDiscovery(confucius, "孔子", { ...emptyDiscoveryFilters, era: "当代" })).toBe(false);
  });

  it("清空筛选对象可恢复人物", () => {
    expect(matchesDiscovery(confucius, "", emptyDiscoveryFilters)).toBe(true);
  });
});

