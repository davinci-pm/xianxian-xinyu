"use client";

import { FormEvent, type ReactNode, useEffect, useState } from "react";
import { SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import type { SessionInfo } from "@/lib/types";

export default function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.session().then(setSession).catch(() => setSession({
      authenticated: false,
      auth_required: true,
      locale: "zh-CN",
      long_memory_available: false,
      display_name: null,
    }));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      setSession(await api.login(code));
      setCode("");
    } catch {
      setError("邀请码无效，请检查后重新输入。");
    } finally {
      setSubmitting(false);
    }
  }

  if (session === null) {
    return <main className="auth-loading"><SparkIcon size={28} /><p>正在确认内测身份…</p></main>;
  }

  if (session.auth_required && !session.authenticated) {
    return (
      <main className="auth-page" id="main-content">
        <section className="auth-card" aria-labelledby="auth-title">
          <div className="auth-seal">先</div>
          <p className="eyebrow"><span /> 邀请制内测</p>
          <h1 id="auth-title">先有一枚通行笺，<br />再与思想同行。</h1>
          <p className="auth-intro">每枚邀请码只对应一位内测用户。登录后，你的谈话与记忆会与其他人严格分开。</p>
          <form onSubmit={submit}>
            <label htmlFor="invite-code">邀请码</label>
            <input
              id="invite-code"
              autoComplete="one-time-code"
              autoFocus
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="请输入你的专属邀请码"
              maxLength={128}
            />
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="button button-primary" disabled={submitting || code.trim().length < 4} type="submit">
              {submitting ? "正在核验…" : "进入先贤心语"}
            </button>
          </form>
          <small>人物对话由生成式模型基于公开资料构建，并非真人本人，也不替代心理、医疗、法律或投资建议。</small>
        </section>
      </main>
    );
  }

  return <>{children}</>;
}
