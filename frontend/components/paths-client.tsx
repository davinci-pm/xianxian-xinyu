"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import CharacterArt from "@/components/character-art";
import { ArrowRightIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { displayPersonaName } from "@/lib/persona-visual";
import type { PersonaCard } from "@/lib/types";

const focusOptions = ["更想看清发生了什么", "更想做出一个决定", "更想停止反复内耗", "更想知道下一步怎么做"];
const feelingOptions = ["焦虑", "迷茫", "委屈", "愤怒", "疲惫", "自我怀疑"];

function rankPersonas(personas: PersonaCard[], concern: string, focus: string, feeling: string) {
  const combined = `${concern} ${focus} ${feeling}`;
  const score = (persona: PersonaCard) => {
    const terms = [...persona.dilemmas, ...persona.topics, ...persona.domains];
    let value = terms.reduce((total, term) => total + (combined.includes(term) || term.split("").some((char) => combined.includes(char)) ? 2 : 0), 0);
    if (persona.slug === "confucius" && /关系|责任|家庭|职场|选择/.test(combined)) value += 6;
    if (persona.slug === "nietzsche" && /自我|怀疑|痛苦|意义|勇气/.test(combined)) value += 6;
    if (persona.slug === "marcus-aurelius" && /焦虑|内耗|控制|下一步|疲惫/.test(combined)) value += 6;
    return value;
  };
  return [...personas].sort((a, b) => score(b) - score(a)).slice(0, 3);
}

export default function PathsClient({ initialConcern }: { initialConcern: string }) {
  const [step, setStep] = useState(initialConcern ? 2 : 1);
  const [concern, setConcern] = useState(initialConcern);
  const [focus, setFocus] = useState("");
  const [feeling, setFeeling] = useState("");
  const [personas, setPersonas] = useState<PersonaCard[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.personas().then(setPersonas).catch(() => setError("暂时无法读取人物资料，请确认本地服务已启动。"));
  }, []);

  const recommendations = useMemo(() => rankPersonas(personas, concern, focus, feeling), [concern, feeling, focus, personas]);

  function submitConcern(event: FormEvent) {
    event.preventDefault();
    if (concern.trim()) setStep(2);
  }

  function submitClue(event: FormEvent) {
    event.preventDefault();
    if (focus && feeling) setStep(3);
  }

  return (
    <main className="paths-page page-shell" id="main-content">
      <header className="paths-header">
        <p className="eyebrow"><span /> 思想路径</p>
        <h1>不确定和谁谈？<br />先从你的处境出发。</h1>
        <p>三步就够。我们不会替你判断，只把最适合此刻的三种思想方法放到你面前。</p>
      </header>

      <ol className="path-progress" aria-label="思想路径进度">
        {["说出困惑", "补充一条线索", "选择同行者"].map((label, index) => {
          const itemStep = index + 1;
          return <li className={itemStep === step ? "active" : itemStep < step ? "done" : ""} key={label}><span>{itemStep < step ? "✓" : itemStep}</span><b>{label}</b></li>;
        })}
      </ol>

      <div className="path-workspace">
        <section className="path-question-card">
          {step === 1 && (
            <form onSubmit={submitConcern}>
              <span className="question-number">01</span>
              <h2>最近哪件事，最让你停在原地？</h2>
              <p>不用把前因后果都交代清楚，一两句话就可以。</p>
              <label htmlFor="path-concern" className="sr-only">当前困惑</label>
              <textarea id="path-concern" autoFocus value={concern} onChange={(event) => setConcern(event.target.value)} rows={6} maxLength={500} placeholder="比如：我拿到一个新机会，但越接近做决定，越担心自己会选错……" />
              <div className="path-form-footer"><small>{concern.length}/500</small><button className="button button-primary" disabled={!concern.trim()} type="submit">继续 <ArrowRightIcon /></button></div>
            </form>
          )}

          {step === 2 && (
            <form onSubmit={submitClue}>
              <button className="back-text" type="button" onClick={() => setStep(1)}>← 修改困惑</button>
              <span className="question-number">02</span>
              <h2>如果这次谈话只带走一样东西，<br />你更希望是什么？</h2>
              <fieldset><legend>你更需要</legend><div className="choice-grid">{focusOptions.map((option) => <button className={focus === option ? "selected" : ""} type="button" key={option} onClick={() => setFocus(option)}>{option}</button>)}</div></fieldset>
              <fieldset><legend>此刻更接近哪种感受</legend><div className="feeling-row">{feelingOptions.map((option) => <button className={feeling === option ? "selected" : ""} type="button" key={option} onClick={() => setFeeling(option)}>{option}</button>)}</div></fieldset>
              <div className="path-form-footer"><span /><button className="button button-primary" disabled={!focus || !feeling} type="submit">看看谁适合我 <ArrowRightIcon /></button></div>
            </form>
          )}

          {step === 3 && (
            <div className="path-result-copy">
              <button className="back-text" type="button" onClick={() => setStep(2)}>← 修改线索</button>
              <span className="question-number">03</span>
              <h2>三种看法，<br />从不同方向照亮这件事。</h2>
              <blockquote>{concern}</blockquote>
              <p>你的回答没有被发送给模型。当前推荐由人物资料中的话题、领域与适合困惑在本地匹配完成。</p>
              <button className="button button-secondary" type="button" onClick={() => { setConcern(""); setFocus(""); setFeeling(""); setStep(1); }}>重新开始</button>
            </div>
          )}
        </section>

        <aside className="path-side-panel">
          {step < 3 ? (
            <>
              <SparkIcon size={30} />
              <h2>我们如何推荐</h2>
              <ul><li>你正在面对的具体处境</li><li>你更需要澄清、决策还是行动</li><li>人物擅长使用的思想方法</li></ul>
              <p>推荐不是心理诊断，也不会替你做决定。</p>
            </>
          ) : (
            <div className="path-recommendations">
              {error && <div className="status-banner status-error">{error}</div>}
              {recommendations.map((persona, index) => (
                <article key={persona.slug} className="path-persona-card">
                  <CharacterArt slug={persona.slug} name={persona.name_zh} variant="mini" />
                  <div><span className="match-label">{index === 0 ? "最契合" : `另一种方向 ${index}`}</span><h3>{displayPersonaName(persona.name_zh)}</h3><p>{persona.short_intro}</p><Link href={`/figures/${persona.slug}?concern=${encodeURIComponent(concern)}`}>先了解 TA <ArrowRightIcon size={16} /></Link></div>
                </article>
              ))}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

