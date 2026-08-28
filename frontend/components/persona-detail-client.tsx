"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import CharacterArt from "@/components/character-art";
import { ArrowRightIcon, ExternalIcon, QuoteIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { displayPersonaName, personaQuotes } from "@/lib/persona-visual";
import type { PersonaDetail } from "@/lib/types";

type DetailTab = "ideas" | "questions" | "views" | "sources";

const tabLabels: Record<DetailTab, string> = {
  ideas: "核心思想",
  questions: "适合讨论",
  views: "代表性观点",
  sources: "资料来源",
};

export default function PersonaDetailClient({ slug, initialConcern = "" }: { slug: string; initialConcern?: string }) {
  const router = useRouter();
  const [persona, setPersona] = useState<PersonaDetail | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>("ideas");
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.persona(slug).then(setPersona).catch(() => setError("没有找到这位人物，或后端服务尚未启动。")).finally(() => setLoading(false));
  }, [slug]);

  const openingPreview = useMemo(() => {
    if (!persona) return "";
    if (initialConcern) return `你提到：“${initialConcern}”。先不急着下结论——这件事里，哪一部分最让你迟迟不能行动？`;
    return personaQuotes[persona.slug] ?? `最近有什么事，让你觉得必须停下来重新想一想？`;
  }, [initialConcern, persona]);

  async function startConversation() {
    if (!persona || starting) return;
    setStarting(true);
    setError(null);
    try {
      const created = await api.createConversation(persona.slug);
      sessionStorage.setItem(`quick-replies:${created.conversation.id}`, JSON.stringify(created.quick_replies));
      if (initialConcern) sessionStorage.setItem(`pending-concern:${created.conversation.id}`, initialConcern);
      router.push(`/chat/${created.conversation.id}`);
    } catch {
      setError("对话暂时无法开始，请确认数据库已经初始化。");
      setStarting(false);
    }
  }

  if (loading) return <main className="detail-loading page-shell" id="main-content"><div className="detail-loading-art" /><p>正在整理人物资料与公开来源…</p></main>;
  if (!persona) return <main className="detail-empty page-shell" id="main-content"><SparkIcon size={34} /><h1>人物资料暂不可用</h1><p>{error}</p><Link className="button button-secondary" href="/">返回人物发现</Link></main>;

  const displayName = displayPersonaName(persona.name_zh);

  return (
    <main className="figure-page" id="main-content">
      <div className="figure-breadcrumb page-shell"><Link href="/">人物发现</Link><span>·</span><b>{displayName}</b></div>
      <section className="figure-hero page-shell">
        <div className="figure-visual">
          <CharacterArt slug={persona.slug} name={persona.name_zh} priority variant="hero" />
          <div className="figure-inscription"><span>{persona.era}</span><span>{persona.region}</span><small>原创 AI 插画 · 非历史照片</small></div>
        </div>
        <div className="figure-intro">
          <p className="eyebrow"><span /> {persona.domains.slice(0, 2).join(" · ")}</p>
          <h1>{displayName}</h1>
          <p className="figure-name-en">{persona.name_en.replace(/ Perspective| Method/g, "")}</p>
          <p className="figure-lead">{persona.short_intro}</p>
          <div className="figure-tags">{persona.topics.slice(0, 4).map((topic) => <span key={topic}>{topic}</span>)}</div>
          <div className="opening-preview">
            <QuoteIcon size={25} />
            <div><small>TA 可能会这样主动开始</small><p>{openingPreview}</p></div>
          </div>
          <button className="button button-primary figure-start" type="button" onClick={startConversation} disabled={starting} data-testid="start-conversation">
            {starting ? "正在准备第一句话…" : "让 TA 主动和我聊聊"}<ArrowRightIcon />
          </button>
          <small className="figure-start-note">开始后会创建真实会话；若有经你确认的记忆，开场会主动接续。</small>
          {error && <div className="status-banner status-error" role="alert">{error}</div>}
        </div>
      </section>

      {persona.is_living && (
        <div className="living-person-notice page-shell" role="note" data-testid="living-person-notice">
          <strong>在世公众人物特别提示</strong><span>这是基于公开资料构建的虚构化 AI 思想人格，非本人、非授权、不代表其真实观点，也不构成投资、医疗、法律或心理治疗建议。</span>
        </div>
      )}

      <section className="figure-content page-shell">
        <div className="figure-tabs" role="tablist" aria-label="人物资料">
          {(Object.keys(tabLabels) as DetailTab[]).map((tab) => (
            <button role="tab" aria-selected={activeTab === tab} id={`tab-${tab}`} aria-controls={`panel-${tab}`} className={activeTab === tab ? "active" : ""} type="button" key={tab} onClick={() => setActiveTab(tab)}>{tabLabels[tab]}</button>
          ))}
        </div>
        <div className="figure-tab-panel" role="tabpanel" id={`panel-${activeTab}`} aria-labelledby={`tab-${activeTab}`}>
          {activeTab === "ideas" && <div className="principle-grid">{persona.principles.map((principle, index) => <article key={principle.id ?? principle.name}><span>{String(index + 1).padStart(2, "0")}</span><h2>{principle.name}</h2><p>{principle.meaning}</p></article>)}</div>}
          {activeTab === "questions" && <div className="discussion-panel"><div><p className="eyebrow"><span /> 从具体处境开始</p><h2>把你的生活放进思想里，<br />而不是背诵一个答案。</h2></div><ol>{persona.suitable_questions.map((question, index) => <li key={question}><span>{index + 1}</span><p>{question}</p></li>)}</ol></div>}
          {activeTab === "views" && <div className="view-list">{persona.representative_views.map((view, index) => <blockquote key={`${view}-${index}`}><QuoteIcon /><p>{view}</p><span>{displayName}思想方法的 AI 概括，不是逐字引语</span></blockquote>)}</div>}
          {activeTab === "sources" && <div className="sources-layout"><div><p className="eyebrow"><span /> 资料边界</p><h2>来源与声明</h2><p>{persona.disclaimer}</p><p>对话中的引用只用于说明知识依据。人物表达由 AI 生成，不代表原人物真实说过这句话。</p></div><ol className="source-panel">{persona.sources.length > 0 ? persona.sources.map((source, index) => <li key={`${source.citation_label}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div>{source.source_url ? <a href={source.source_url} target="_blank" rel="noreferrer">{source.title}<ExternalIcon size={14} /></a> : <strong>{source.title}</strong>}<small>{source.license_note}</small></div></li>) : <li><div><strong>资料仍在扩充</strong><small>当前使用结构化思想原则与人物资料。</small></div></li>}</ol></div>}
        </div>
      </section>

      <div className="mobile-start-bar"><div><strong>{displayName}</strong><small>AI 思想人格 · 非真人本人</small></div><button className="button button-primary" type="button" disabled={starting} onClick={startConversation}>开始对话 <ArrowRightIcon size={17} /></button></div>
    </main>
  );
}

