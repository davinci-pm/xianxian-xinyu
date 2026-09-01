"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { ArrowRightIcon, BookIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import type { PersonaTargetType, StudioHealthReport } from "@/lib/types";

interface UploadDraft {
  name: string;
  type: string;
  content: string;
  chars: number;
}

const targetTypes: Array<{ value: PersonaTargetType; label: string; note: string }> = [
  { value: "self", label: "我自己", note: "日记、文章与决策复盘最有价值" },
  { value: "authorized_private", label: "我熟悉的人", note: "适合经授权的亲友、同事或导师" },
  { value: "deceased", label: "已经离开的人", note: "从留下的文字与对话中保留思想痕迹" },
  { value: "composite", label: "合成人物", note: "从多组材料中提炼共同模式" },
  { value: "fictional", label: "原创角色", note: "用设定、台词和故事塑造稳定人格" },
  { value: "public_figure", label: "公众人物", note: "使用来源清晰的一手公开资料" },
];

const sourceTypes = [
  { value: "chat", label: "聊天记录" },
  { value: "writing", label: "文章 / 日记 / 邮件" },
  { value: "interview", label: "访谈 / 语音转写" },
  { value: "public_statements", label: "公开表达资料包" },
  { value: "social", label: "社交平台公开表达" },
  { value: "speech", label: "演讲 / 公开发言" },
  { value: "timeline", label: "人生时间线" },
  { value: "text", label: "其他文本" },
];

const soulPipeline = [
  { key: "evidence", label: "证据层", note: "微信说话人分离、上下文保留、去重与真实回复留出" },
  { key: "cognition", label: "认知层", note: "事件、决策样本、价值排序、条件规则与观点变化" },
  { key: "retrieval", label: "检索层", note: "私有资料、时间线与联网公开事实分层召回" },
  { key: "generation", label: "生成层", note: "情境人格激活、深思草稿、边界与反例二次自检" },
  { key: "learning", label: "验证层", note: "盲测留出、用户纠正、版本回归与 LoRA 资格门" },
];

const tierCopy = {
  outline: { label: "轮廓提炼", note: "先建立表达与证据骨架" },
  structured: { label: "结构化蒸馏", note: "已能进行上下文与决策建模" },
  deep: { label: "深层蒸馏", note: "可做真实回复盲测与时间人格分析" },
  trainable: { label: "训练候选", note: "达到 LoRA 数据门槛，仍需盲测证明有必要" },
};

const capabilityCopy: Record<string, string> = {
  style_profile: "语气指纹",
  evidence_retrieval: "证据检索",
  decision_model: "决策模型",
  context_activation: "情境激活",
  blind_holdout: "真实盲测",
  temporal_persona: "时间人格",
  lora_candidate: "LoRA 候选",
};

export default function PersonaStudioWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [targetType, setTargetType] = useState<PersonaTargetType>("self");
  const [relationship, setRelationship] = useState("");
  const [purpose, setPurpose] = useState("");
  const [files, setFiles] = useState<UploadDraft[]>([]);
  const [sourceType, setSourceType] = useState("chat");
  const [targetSpeaker, setTargetSpeaker] = useState("");
  const [timeRange, setTimeRange] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [publishedAt, setPublishedAt] = useState("");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [coreValues, setCoreValues] = useState("");
  const [decisionCase, setDecisionCase] = useState("");
  const [neverDo, setNeverDo] = useState("");
  const [unlikeResponse, setUnlikeResponse] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [health, setHealth] = useState<StudioHealthReport | null>(null);
  const [pipelineStage, setPipelineStage] = useState(0);

  useEffect(() => {
    if (!submitting || step !== 4) return;
    const timer = window.setInterval(() => {
      setPipelineStage((current) => Math.min(current + 1, soulPipeline.length - 1));
    }, 900);
    return () => window.clearInterval(timer);
  }, [submitting, step]);

  const totalChars = useMemo(() => files.reduce((sum, file) => sum + file.chars, 0), [files]);
  const canContinueProfile = name.trim().length > 0 && purpose.trim().length >= 8;
  const canDistill = canContinueProfile && files.length > 0 && totalChars >= 800 && rightsConfirmed;

  async function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    setError(null);
    const selected = Array.from(event.target.files ?? []);
    const accepted = new Set(["txt", "md", "csv", "json", "jsonl"]);
    const next: UploadDraft[] = [];
    for (const file of selected) {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (!accepted.has(extension)) {
        setError(`${file.name} 暂不支持。请选择 TXT、Markdown、CSV、JSON 或 JSONL。`);
        continue;
      }
      const content = await file.text();
      if (content.length > 500_000) {
        setError(`${file.name} 超过内测版单文件 50 万字符限制。`);
        continue;
      }
      next.push({ name: file.name, type: file.type || "text/plain", content, chars: content.length });
    }
    setFiles((current) => [...current, ...next].filter((item, index, all) => all.findIndex((candidate) => candidate.name === item.name) === index));
    event.target.value = "";
  }

  function calibrationPayload() {
    return {
      core_values: coreValues.trim(),
      decision_case: decisionCase.trim(),
      never_do: neverDo.trim(),
      unlike_response: unlikeResponse.trim(),
    };
  }

  async function analyze() {
    if (!canDistill) return;
    setSubmitting(true);
    setError(null);
    try {
      let activeProjectId = projectId;
      if (!activeProjectId) {
        const project = await api.createStudioProject({
          name: name.trim(),
          target_type: targetType,
          relationship: relationship.trim(),
          purpose: purpose.trim(),
          language: "zh-CN",
        });
        activeProjectId = project.id;
        setProjectId(project.id);
        await Promise.all(files.map((file) => api.addStudioSource(project.id, {
          filename: file.name,
          source_type: sourceType,
          mime_type: file.type,
          content: file.content,
          target_speaker: targetSpeaker.trim() || null,
          time_range: timeRange.trim() || null,
          source_url: sourceUrl.trim() || null,
          published_at: publishedAt.trim() || null,
          rights_confirmed: rightsConfirmed,
        })));
      }
      const report = await api.analyzeStudioProject(activeProjectId, calibrationPayload());
      setHealth(report);
      setStep(4);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "资料分析失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  }

  async function finish() {
    if (!projectId || !health?.can_distill) return;
    setPipelineStage(0);
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.distillStudioProject(projectId, calibrationPayload());
      router.push(`/me?created=${encodeURIComponent(result.persona.slug)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "生成失败，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="studio-page page-shell" id="main-content">
      <header className="studio-heading">
        <div>
          <p className="eyebrow"><span /> 女娲工坊 · 内测</p>
          <h1>把一个人留下的痕迹，<br />整理成可以继续对话的思想资产。</h1>
        </div>
        <p>不用写提示词。告诉我们是谁、上传他真实留下的表达，再补充几个关键判断。</p>
      </header>

      <ol className="studio-progress" aria-label="创建进度" style={{ "--studio-progress": (step - 1) / 3 } as CSSProperties}>
        {["人物基础卡", "上传资料", "校准判断", "质量体检"].map((label, index) => (
          <li className={step === index + 1 ? "active" : step > index + 1 ? "done" : ""} key={label}>
            <span>{String(index + 1).padStart(2, "0")}</span><b>{label}</b>
          </li>
        ))}
      </ol>

      <section className="studio-workspace">
        {step === 1 && (
          <div className="studio-form-panel studio-step-panel">
            <p className="form-kicker">第一步</p>
            <h2>你想留下谁？</h2>
            <div className="studio-field">
              <label htmlFor="persona-name">心智分身的名称</label>
              <input id="persona-name" maxLength={80} onChange={(event) => setName(event.target.value)} placeholder="可以是真名，也可以只是你熟悉的称呼" value={name} />
            </div>
            <fieldset className="studio-fieldset">
              <legend>人物类型</legend>
              <div className="target-type-grid">
                {targetTypes.map((item) => (
                  <button className={targetType === item.value ? "selected" : ""} key={item.value} onClick={() => setTargetType(item.value)} type="button">
                    <strong>{item.label}</strong><small>{item.note}</small>
                  </button>
                ))}
              </div>
            </fieldset>
            <div className="studio-field two-column">
              <div><label htmlFor="relationship">你们的关系</label><input id="relationship" maxLength={80} onChange={(event) => setRelationship(event.target.value)} placeholder="例如：自己、朋友、父亲、导师" value={relationship} /></div>
              <div><label htmlFor="purpose">希望他陪你做什么</label><input id="purpose" maxLength={1000} onChange={(event) => setPurpose(event.target.value)} placeholder="例如：在选择困难时给我熟悉的判断" value={purpose} /></div>
            </div>
            <div className="studio-actions"><span /><button className="button button-primary" disabled={!canContinueProfile} onClick={() => setStep(2)} type="button">继续上传资料 <ArrowRightIcon /></button></div>
          </div>
        )}

        {step === 2 && (
          <div className="studio-form-panel studio-step-panel">
            <p className="form-kicker">第二步</p>
            <h2>上传他真实留下的表达。</h2>
            <div className="source-meta-grid">
              <div className="studio-field"><label htmlFor="source-type">这批资料是什么</label><select id="source-type" onChange={(event) => setSourceType(event.target.value)} value={sourceType}>{sourceTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>
              <div className="studio-field"><label htmlFor="speaker">目标说话人</label><input id="speaker" onChange={(event) => setTargetSpeaker(event.target.value)} placeholder="聊天记录里显示的名字，可不填" value={targetSpeaker} /></div>
              <div className="studio-field"><label htmlFor="time-range">资料时间范围</label><input id="time-range" onChange={(event) => setTimeRange(event.target.value)} placeholder="例如：2020—2026" value={timeRange} /></div>
            </div>
            <div className="studio-field two-column source-origin-grid">
              <div><label htmlFor="source-url">原始来源 URL</label><input id="source-url" onChange={(event) => setSourceUrl(event.target.value)} placeholder="选填，用于回答证据追溯" type="url" value={sourceUrl} /></div>
              <div><label htmlFor="published-at">发布日期</label><input id="published-at" onChange={(event) => setPublishedAt(event.target.value)} placeholder="例如：2024-06-18" value={publishedAt} /></div>
            </div>
            <label className="upload-dropzone">
              <BookIcon size={28} />
              <strong>选择资料文件</strong>
              <span>支持 TXT、Markdown、CSV、JSON、JSONL；可多选</span>
              <input accept=".txt,.md,.csv,.json,.jsonl,text/plain,text/markdown,text/csv,application/json" multiple onChange={selectFiles} type="file" />
            </label>
            {files.length > 0 && <div className="upload-list">{files.map((file) => <div key={file.name}><span>{file.name}</span><small>{file.chars.toLocaleString("zh-CN")} 字符</small><button aria-label={`移除 ${file.name}`} onClick={() => setFiles((current) => current.filter((item) => item.name !== file.name))} type="button">移除</button></div>)}</div>}
            <div className="data-health"><span style={{ width: `${Math.min(totalChars / 10_000, 1) * 100}%` }} /><div><strong>{totalChars.toLocaleString("zh-CN")} 个字符</strong><small>{totalChars < 800 ? "至少需要 800 个目标人物有效字符" : totalChars < 5_000 ? "可建立人物轮廓；更多上下文对话会提升稳定性" : totalChars < 10_000 ? "已可做结构化蒸馏；优先补真实选择与前后对话" : "资料量充足，最终像不像仍以独立盲测为准"}</small></div></div>
            <label className="rights-check"><input checked={rightsConfirmed} onChange={(event) => setRightsConfirmed(event.target.checked)} type="checkbox" /><span>我确认有权在本次私人内测中使用这些资料，并已移除无关第三方隐私。</span></label>
            <div className="studio-actions"><button className="button button-secondary" onClick={() => setStep(1)} type="button">返回</button><button className="button button-primary" disabled={files.length === 0 || totalChars < 800 || !rightsConfirmed} onClick={() => setStep(3)} type="button">继续校准 <ArrowRightIcon /></button></div>
          </div>
        )}

        {step === 3 && (
          <div className="studio-form-panel studio-step-panel">
            <p className="form-kicker">第三步</p>
            <h2>补上语料不容易说清的部分。</h2>
            <p className="studio-form-intro">这些问题不是必填，但它们往往比继续堆聊天记录更能提高人物质量。</p>
            <div className="calibration-grid">
              <label><span>他最看重的三件事</span><textarea maxLength={2000} onChange={(event) => setCoreValues(event.target.value)} placeholder="例如：诚实、长期投入、对家人的责任" value={coreValues} /></label>
              <label><span>最能说明他判断方式的一次选择</span><textarea maxLength={3000} onChange={(event) => setDecisionCase(event.target.value)} placeholder="当时面对什么、怎么判断、最后怎么做" value={decisionCase} /></label>
              <label><span>他大概率绝不会做什么</span><textarea maxLength={2000} onChange={(event) => setNeverDo(event.target.value)} placeholder="价值底线、不能接受的行为" value={neverDo} /></label>
              <label><span>哪种回答听起来聪明，却最不像他</span><textarea maxLength={2000} onChange={(event) => setUnlikeResponse(event.target.value)} placeholder="帮助系统识别人物的反例" value={unlikeResponse} /></label>
            </div>
            <aside className="distill-summary"><SparkIcon size={24} /><div><strong>即将生成“{name || "未命名人物"}”</strong><p>{files.length} 份资料 · {totalChars.toLocaleString("zh-CN")} 字符 · 默认仅你的账号可见</p></div></aside>
            {error && <div className="status-banner status-error" role="alert">{error}</div>}
            <div className="studio-actions"><button className="button button-secondary" disabled={submitting} onClick={() => setStep(projectId ? 4 : 2)} type="button">{projectId ? "返回体检" : "返回"}</button><button className="button button-primary" disabled={!canDistill || submitting} onClick={analyze} type="button">{submitting ? "正在分析资料…" : projectId ? "重新计算质量" : "先做质量体检"} <ArrowRightIcon size={17} /></button></div>
          </div>
        )}

        {step === 4 && health && (
          <div className="studio-form-panel studio-step-panel health-panel">
            <p className="form-kicker">第四步</p>
            <div className="health-hero">
              <div><span>{tierCopy[health.adaptive_tier].label}</span><h2>{health.readiness_level}</h2><p>{health.metric_scope}。当前 {health.overall_score}/100 只用于判断资料还缺什么。</p></div>
              <strong style={{ "--health-score": `${health.overall_score * 3.6}deg` } as CSSProperties}>{health.overall_score}</strong>
            </div>
            <section className="adaptive-summary">
              <div><small>本次蒸馏策略</small><strong>{tierCopy[health.adaptive_tier].label}</strong><span>{tierCopy[health.adaptive_tier].note}</span></div>
              <div><small>微信上下文</small><strong>{health.data_profile.contextual_target_turns}</strong><span>{health.data_profile.holdout_ready ? "已建立独立盲测回复" : "继续补充成对上下文可开启盲测"}</span></div>
              <div className="capability-cloud"><small>已启用能力</small><p>{health.enabled_capabilities.map((item) => <span key={item}>{capabilityCopy[item] ?? item}</span>)}</p></div>
            </section>
            <div className="health-dimensions">
              {health.dimensions.map((dimension) => (
                <article className={dimension.status} key={dimension.key}>
                  <header><span>{dimension.label}</span><b>{dimension.score}</b></header>
                  <i><span style={{ width: `${dimension.score}%` }} /></i>
                  <p>{dimension.detail}</p>
                </article>
              ))}
            </div>
            <div className="health-evidence-summary">
              <div><b>{health.substantive_utterances}</b><span>完整表达</span></div>
              <div><b>{health.decision_signals}</b><span>决策证据</span></div>
              <div><b>{health.domains_covered.length}</b><span>生活情境</span></div>
            </div>
            <section className="health-gaps">
              <div><h3>现在最值得补的资料</h3><ol>{health.gaps.map((gap) => <li key={gap}>{gap}</li>)}</ol></div>
              <div><h3>可以直接去问的校准问题</h3><ol>{health.recommended_questions.map((question) => <li key={question}>{question}</li>)}</ol></div>
            </section>
            <section className="soul-pipeline-preview">
              <header><span>灵魂蒸馏流水线</span><p>点击生成后，每份用户上传资料都会完整走过这五层。</p></header>
              <ol>{soulPipeline.map((stage, index) => <li key={stage.key}><b>{String(index + 1).padStart(2, "0")}</b><div><strong>{stage.label}</strong><span>{stage.note}</span></div></li>)}</ol>
            </section>
            {submitting && <section className="distill-live" aria-live="polite">
              <div className="distill-orbit"><SparkIcon size={20} /></div>
              <div><small>Soul V3 正在运行</small><strong>{soulPipeline[pipelineStage].label}</strong><p>{soulPipeline[pipelineStage].note}</p></div>
              <ol>{soulPipeline.map((stage, index) => <li className={index < pipelineStage ? "done" : index === pipelineStage ? "active" : ""} key={stage.key}><i /><span>{stage.label}</span></li>)}</ol>
            </section>}
            {error && <div className="status-banner status-error" role="alert">{error}</div>}
            <div className="studio-actions"><button className="button button-secondary" disabled={submitting} onClick={() => setStep(3)} type="button">回去补充校准</button><button className="button button-primary" disabled={!health.can_distill || submitting} onClick={finish} type="button">{submitting ? "正在执行五层灵魂蒸馏…" : "开始灵魂蒸馏"} <SparkIcon size={17} /></button></div>
          </div>
        )}

        <aside className="studio-side-note">
          <span>女娲 · 造人记</span>
          <blockquote>真正有价值的不是复读一个人说过什么，而是保留他如何判断、何时犹豫，以及哪些事绝不妥协。</blockquote>
          <ul><li>人物资料与聊天记忆分开保存</li><li>核心判断尽量绑定原始证据</li><li>生成后进入“我的心智分身”</li></ul>
        </aside>
      </section>
    </main>
  );
}
