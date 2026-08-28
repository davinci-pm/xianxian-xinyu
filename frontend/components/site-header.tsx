"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { BookIcon, CloseIcon, MemoryIcon, MenuIcon, SparkIcon } from "@/components/icons";

const links = [
  { href: "/", label: "人物发现" },
  { href: "/paths", label: "思想路径" },
  { href: "/notes", label: "心语札记" },
];

export default function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const inChat = pathname.startsWith("/chat/");

  return (
    <header className={inChat ? "site-header site-header-chat" : "site-header"}>
      <Link href="/" className="brand" aria-label="返回先贤心语首页" onClick={() => setOpen(false)}>
        <span className="brand-mark">先</span>
        <span className="brand-copy"><strong>先贤心语</strong><small>与思想同行，而非向答案投降</small></span>
      </Link>
      <nav className="desktop-nav" aria-label="主导航">
        {links.map((link) => (
          <Link className={pathname === link.href ? "active" : ""} href={link.href} key={link.href}>{link.label}</Link>
        ))}
      </nav>
      <div className="header-actions">
        <span className="ai-badge"><SparkIcon size={14} /> AI 思想人格 · 非真人本人</span>
        <Link href="/settings/memory" className="icon-link" aria-label="记忆设置"><MemoryIcon size={19} /></Link>
        <button className="mobile-menu-button" type="button" aria-label={open ? "关闭菜单" : "打开菜单"} aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>
      {open && (
        <nav className="mobile-nav" aria-label="移动端主导航">
          {links.map((link) => <Link href={link.href} key={link.href} onClick={() => setOpen(false)}>{link.label}</Link>)}
          <Link href="/settings/memory" onClick={() => setOpen(false)}><MemoryIcon size={18} /> 记忆设置</Link>
          <span><BookIcon size={18} /> 基于公开资料构建的 AI 思想人格</span>
        </nav>
      )}
    </header>
  );
}

