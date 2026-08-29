"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CharacterArt from "@/components/character-art";
import { ArrowRightIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import type { ConversationSummary, OwnedPersona } from "@/lib/types";

export default function MyPersonasDashboard() {
  const router = useRouter();
  const [personas, setPersonas] = useState<OwnedPersona[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [starting, setStarting] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.ownedPersonas(), api.conversations()])
      .then(([owned, recent]) => { setPersonas(owned); setConversations(recent.slice(0, 4)); })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "暂时无法读取你的心智分身。"))
      .finally(() => setLoading(false));
  }, []);

  async function startConversation(persona: OwnedPersona) {
    setStarting(persona.slug);
    setError(null);
    try {
      const result = await api.createConversation(persona.slug);
      router.push(`/chat/${result.conversation.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "暂时无法开始对话。");
      setStarting(null);
    }
  }

  return (
    <main className="my-personas-page" id="main-content">
      <section className="my-personas-hero page-shell">
        <div><p className="eyebrow"><span /> 我的主页</p><h1>你留下的人，<br />都在这里继续生长。</h1><p>每个心智分身只属于你的账号。可以继续聊天、补充资料，或回到某个旧版本。</p></div>
        <Link className="button button-primary" href="/studio/new">创建心智分身 <SparkIcon size={17} /></Link>
      </section>

      <section className="my-personas-section page-shell">
        <header className="section-heading"><div><p className="eyebrow"><span /> 我的心智分身</p><h2>私人思想资产</h2></div><Link className="text-link" href="/studio">进入女娲工坊 <ArrowRightIcon /></Link></header>
        {loading && <div className="persona-grid" aria-label="正在载入心智分身"><div className="persona-card persona-skeleton" /></div>}
        {error && <div className="status-banner status-error" role="alert">{error}</div>}
        {!loading && personas.length === 0 && <div className="my-personas-empty"><div className="empty-seal">娲</div><h3>还没有属于你的心智分身</h3><p>上传一份聊天记录、几封邮件或一组文章，先生成一个只对你可见的初版。</p><Link className="button button-primary" href="/studio/new">去创建第一个心智分身</Link></div>}
        <div className="owned-persona-grid">
          {personas.map((persona) => (
            <article className="owned-persona-card" key={persona.id}>
              <CharacterArt name={persona.name_zh} slug={persona.slug} variant="card" />
              <div className="owned-persona-copy">
                <div className="owned-persona-meta"><span>仅自己可见</span><span>V{persona.version}</span></div>
                <h3>{persona.name_zh}</h3><p>{persona.short_intro}</p>
                <div className="owned-quality"><span style={{ width: `${persona.quality_score}%` }} /><small>资料质量 {persona.quality_score}/100</small></div>
                <div className="tag-row">{persona.topics.slice(0, 3).map((topic) => <span key={topic}>{topic}</span>)}</div>
                <div className="owned-persona-actions"><button className="button button-primary" disabled={starting === persona.slug} onClick={() => startConversation(persona)} type="button">{starting === persona.slug ? "正在进入…" : "开始对话"}</button><Link className="button button-secondary" href={`/figures/${persona.slug}`}>查看人物</Link></div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {conversations.length > 0 && <section className="recent-section page-shell"><header className="section-heading compact"><div><p className="eyebrow"><span /> 最近谈过</p><h2>从停下的地方继续</h2></div></header><div className="recent-list">{conversations.map((conversation) => <Link href={`/chat/${conversation.id}`} key={conversation.id}><span className="recent-persona">{conversation.persona_name}</span><div><strong>{conversation.title}</strong><small>{conversation.short_summary ?? "刚刚开始的对话"}</small></div><span className="recent-stage">{conversation.stage}</span><ArrowRightIcon /></Link>)}</div></section>}
    </main>
  );
}
