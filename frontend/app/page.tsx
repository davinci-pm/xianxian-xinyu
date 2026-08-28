"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import CharacterArt from "@/components/character-art";
import { ArrowRightIcon, SearchIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { emptyDiscoveryFilters, matchesDiscovery, type DiscoveryFilters, type FilterGroup } from "@/lib/discovery";
import { displayPersonaName, personaQuotes } from "@/lib/persona-visual";
import type { ConversationSummary, PersonaCard } from "@/lib/types";

const featuredOrder = ["confucius", "nietzsche", "marcus-aurelius"];
const concernExamples = ["我不知道该不该离开现在的工作", "最近总在自我怀疑", "一段关系让我很疲惫"];

function unique(items: string[], limit = 7) {
  return Array.from(new Set(items)).slice(0, limit);
}

export default function HomePage() {
  const router = useRouter();
  const [personas, setPersonas] = useState<PersonaCard[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [filters, setFilters] = useState<DiscoveryFilters>(emptyDiscoveryFilters);
  const [search, setSearch] = useState("");
  const [concern, setConcern] = useState("");
  const [visibleCount, setVisibleCount] = useState(9);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.personas(), api.conversations()])
      .then(([personaData, conversationData]) => {
        setPersonas(personaData);
        setConversations(conversationData.slice(0, 3));
      })
      .catch(() => setError("暂时无法连接本地服务，请确认前后端已经启动。"));
  }, []);

  const featured = useMemo(() => featuredOrder.map((slug) => personas.find((item) => item.slug === slug)).filter(Boolean) as PersonaCard[], [personas]);
  const options = useMemo(() => ({
    era: unique(personas.map((item) => item.era), 6),
    domain: unique(personas.flatMap((item) => item.domains), 8),
    topic: unique(personas.flatMap((item) => item.topics), 8),
    dilemma: unique(personas.flatMap((item) => item.dilemmas), 8),
  }), [personas]);
  const filtered = useMemo(() => personas.filter((persona) => matchesDiscovery(persona, search, filters)), [filters, personas, search]);
  const hasFilters = search.trim() !== "" || Object.values(filters).some((value) => value !== "全部");

  function updateFilter(group: FilterGroup, value: string) {
    setFilters((current) => ({ ...current, [group]: value }));
    setVisibleCount(9);
  }

  function submitConcern(event: FormEvent) {
    event.preventDefault();
    const value = concern.trim();
    router.push(value ? `/paths?concern=${encodeURIComponent(value)}` : "/paths");
  }

  return (
    <main id="main-content">
      <section className="home-hero page-shell">
        <div className="home-hero-copy">
          <p className="eyebrow"><span /> 一场由思想主动开启的谈话</p>
          <h1>你不必先想好<br />所有的问题。</h1>
          <p className="hero-lead">把此刻说不清的困惑放在这里。一位思想同行者会主动追问、澄清与挑战，陪你形成自己的判断。</p>
          <div className="hero-actions">
            <a className="button button-primary" href="#discover">寻找思想同行者 <ArrowRightIcon /></a>
            <Link className="text-link" href="/paths"><SparkIcon /> 不知道选谁？走一条思想路径</Link>
          </div>
          <form className="concern-box" onSubmit={submitConcern}>
            <label htmlFor="concern-input">此刻，什么事情最困扰你？</label>
            <div>
              <input id="concern-input" value={concern} onChange={(event) => setConcern(event.target.value)} placeholder="不用完整，从最难说清的那一点开始…" maxLength={240} />
              <button type="submit" aria-label="从当前困惑开始"><ArrowRightIcon /></button>
            </div>
            <div className="concern-examples" aria-label="困惑示例">
              {concernExamples.map((example) => <button type="button" key={example} onClick={() => setConcern(example)}>{example}</button>)}
            </div>
          </form>
        </div>
        <div className="hero-gallery" aria-label="推荐思想人物">
          {featured.map((persona, index) => (
            <Link href={`/figures/${persona.slug}`} className={`hero-portrait-card hero-portrait-${index + 1}`} key={persona.slug}>
              <CharacterArt slug={persona.slug} name={persona.name_zh} priority variant="card" />
              <span><b>{displayPersonaName(persona.name_zh)}</b><small>{persona.era}</small></span>
            </Link>
          ))}
          {featured.length === 0 && <div className="hero-gallery-skeleton" aria-hidden="true" />}
          <p className="hero-annotation">思想不是答案，<br />而是一种更清醒的看法。</p>
        </div>
      </section>

      <section className="method-strip" aria-label="产品工作方式">
        <div><span>01</span><p><strong>主动开启</strong>不等你组织好问题</p></div>
        <div><span>02</span><p><strong>持续追问</strong>从处境走向根因</p></div>
        <div><span>03</span><p><strong>交还判断</strong>留下你的行动札记</p></div>
      </section>

      <section className="discovery-section page-shell" id="discover">
        <header className="section-heading">
          <div><p className="eyebrow"><span /> 人物发现</p><h2>此刻，你更想和谁谈谈？</h2></div>
          <p>按时代、领域、话题或当前困惑筛选。每个人物都由结构化思想原则与公开资料驱动。</p>
        </header>

        <div className="discovery-toolbar">
          <label className="search-field"><SearchIcon /><span className="sr-only">搜索人物或话题</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索人物、思想或话题" /></label>
          {hasFilters && <button className="clear-button" type="button" onClick={() => { setFilters(emptyDiscoveryFilters); setSearch(""); }} data-testid="clear-filters">清空筛选</button>}
        </div>
        <div className="filter-stack">
          {([ ["era", "时代"], ["domain", "领域"], ["topic", "话题"], ["dilemma", "当前困惑"] ] as Array<[FilterGroup, string]>).map(([group, label]) => (
            <div className="filter-group" key={group}>
              <strong>{label}</strong>
              <div>
                {["全部", ...options[group]].map((value) => (
                  <button type="button" key={value} className={filters[group] === value ? "active" : ""} onClick={() => updateFilter(group, value)}>{value}</button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {error && <div className="status-banner status-error" role="alert">{error}</div>}
        {!error && personas.length === 0 && <div className="persona-grid" aria-label="正在载入人物">{[1, 2, 3].map((item) => <div className="persona-card persona-skeleton" key={item} />)}</div>}
        <div className="persona-grid" data-testid="persona-grid">
          {filtered.slice(0, visibleCount).map((persona, index) => (
            <Link className="persona-card" href={`/figures/${persona.slug}`} key={persona.id} data-testid={`persona-card-${persona.slug}`}>
              <CharacterArt slug={persona.slug} name={persona.name_zh} priority={index < 3} variant="card" />
              <div className="persona-card-body">
                <div className="card-meta"><span>{persona.era}</span><span>{persona.region}</span></div>
                <h3>{displayPersonaName(persona.name_zh)}</h3>
                <p className="name-en">{persona.name_en.replace(/ Perspective| Method/g, "")}</p>
                <p className="persona-quote">“{personaQuotes[persona.slug] ?? persona.short_intro}”</p>
                <div className="tag-row">{persona.topics.slice(0, 3).map((topic) => <span key={topic}>{topic}</span>)}</div>
                <span className="card-link">了解并开始对话 <ArrowRightIcon size={17} /></span>
              </div>
            </Link>
          ))}
        </div>
        {filtered.length === 0 && <div className="empty-state"><SparkIcon size={30} /><h3>没有完全符合的思想同行者</h3><p>换一个筛选条件，或直接从当前困惑开始思想路径。</p><button className="button button-secondary" type="button" onClick={() => { setFilters(emptyDiscoveryFilters); setSearch(""); }}>清空筛选</button></div>}
        {visibleCount < filtered.length && <div className="load-more"><button className="button button-secondary" type="button" onClick={() => setVisibleCount((count) => count + 9)}>再看一些人物 <span>{visibleCount}/{filtered.length}</span></button></div>}
      </section>

      {conversations.length > 0 && (
        <section className="recent-section page-shell">
          <header className="section-heading compact"><div><p className="eyebrow"><span /> 未说完的对话</p><h2>从上次停下的地方继续</h2></div><Link className="text-link" href="/notes">查看心语札记 <ArrowRightIcon /></Link></header>
          <div className="recent-list">
            {conversations.map((conversation) => (
              <Link href={`/chat/${conversation.id}`} key={conversation.id}>
                <span className="recent-persona">{displayPersonaName(conversation.persona_name)}</span>
                <div><strong>{conversation.title}</strong><small>{conversation.short_summary ?? "刚刚开始的对话"}</small></div>
                <span className="recent-stage">{conversation.stage}</span><ArrowRightIcon />
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
