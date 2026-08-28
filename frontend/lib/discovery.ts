import type { PersonaCard } from "@/lib/types";

export type FilterGroup = "era" | "domain" | "topic" | "dilemma";
export type DiscoveryFilters = Record<FilterGroup, string>;

export const emptyDiscoveryFilters: DiscoveryFilters = { era: "全部", domain: "全部", topic: "全部", dilemma: "全部" };

export function matchesDiscovery(persona: PersonaCard, search: string, filters: DiscoveryFilters) {
  const text = [persona.name_zh, persona.name_en, persona.short_intro, ...persona.domains, ...persona.topics, ...persona.dilemmas].join(" ").toLowerCase();
  return (!search || text.includes(search.toLowerCase()))
    && (filters.era === "全部" || persona.era === filters.era)
    && (filters.domain === "全部" || persona.domains.includes(filters.domain))
    && (filters.topic === "全部" || persona.topics.includes(filters.topic))
    && (filters.dilemma === "全部" || persona.dilemmas.includes(filters.dilemma));
}

