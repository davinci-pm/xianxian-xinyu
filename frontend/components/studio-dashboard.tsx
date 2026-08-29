"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRightIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import type { StudioProject } from "@/lib/types";

const statusLabels: Record<string, string> = {
  draft: "等待资料",
  sources_ready: "可以蒸馏",
  ready: "人物已生成",
};

export default function StudioDashboard() {
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.studioProjects().then(setProjects).catch((caught) => setError(caught instanceof Error ? caught.message : "暂时无法读取人物草稿。" )).finally(() => setLoading(false));
  }, []);

  return (
    <main className="studio-dashboard page-shell" id="main-content">
      <header className="studio-dashboard-hero">
        <div><p className="eyebrow"><span /> 女娲工坊</p><h1>不是模仿一个口吻，<br />而是整理一套留下来的判断。</h1><p>从聊天、文章和人生片段中提炼心智分身。生成后，它会回到你的个人主页。</p></div>
        <Link className="button button-primary" href="/studio/new">创建一个心智分身 <ArrowRightIcon /></Link>
      </header>
      <section className="studio-projects">
        <header><div><span>人物草稿</span><h2>正在塑形</h2></div><Link href="/me">查看我的心智分身 <ArrowRightIcon size={16} /></Link></header>
        {loading && <div className="studio-empty"><SparkIcon /><p>正在整理你的工坊…</p></div>}
        {error && <div className="status-banner status-error" role="alert">{error}</div>}
        {!loading && !error && projects.length === 0 && <div className="studio-empty"><SparkIcon size={30} /><h3>工坊里还没有人物草稿</h3><p>从一份聊天记录或一组文章开始，不必一次准备完所有资料。</p><Link className="button button-secondary" href="/studio/new">开始第一次蒸馏</Link></div>}
        <div className="studio-project-grid">
          {projects.map((project, index) => (
            <article key={project.id}>
              <span className="project-number">{String(index + 1).padStart(2, "0")}</span>
              <div className="project-state"><i className={project.status === "ready" ? "ready" : ""} />{statusLabels[project.status] ?? project.status}</div>
              <h3>{project.name}</h3><p>{project.purpose}</p>
              <dl><div><dt>资料</dt><dd>{project.sources.length} 份</dd></div><div><dt>字符</dt><dd>{project.source_char_count.toLocaleString("zh-CN")}</dd></div><div><dt>质量</dt><dd>{project.quality_score || "—"}</dd></div></dl>
              {project.persona_slug ? <Link href={`/figures/${project.persona_slug}`}>查看人物 <ArrowRightIcon size={16} /></Link> : <span className="project-next">继续补充资料</span>}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
