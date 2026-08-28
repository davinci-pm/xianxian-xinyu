import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import SiteHeader from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: "先贤心语｜与思想人格展开一场主动对话",
  description: "从公开资料构建的 AI 思想人格，陪你理解困惑、澄清选择并形成自己的判断。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">跳到主要内容</a>
        <SiteHeader />
        {children}
        <footer className="site-footer">
          <div>
            <Link href="/" className="footer-brand">先贤心语</Link>
            <p>基于公开资料构建的 AI 思想人格，不代表人物本人或任何机构。</p>
          </div>
          <nav aria-label="页脚导航">
            <Link href="/paths">思想路径</Link>
            <Link href="/notes">心语札记</Link>
            <Link href="/settings/memory">记忆设置</Link>
          </nav>
          <p>本产品不是心理治疗、医疗、法律或投资建议工具。</p>
        </footer>
      </body>
    </html>
  );
}
