"use client";

import { useEffect, useRef } from "react";
import { CloseIcon } from "@/components/icons";

export default function Drawer({ title, eyebrow, open, onClose, children }: { title: string; eyebrow?: string; open: boolean; onClose: () => void; children: React.ReactNode }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const focusable = Array.from(drawerRef.current?.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input, textarea, [tabindex]:not([tabindex='-1'])") ?? []);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable.at(-1)!;
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previousFocus.current?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
      <section ref={drawerRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header><div>{eyebrow && <small>{eyebrow}</small>}<h2 id="drawer-title">{title}</h2></div><button ref={closeRef} type="button" aria-label="关闭面板" onClick={onClose}><CloseIcon /></button></header>
        <div className="drawer-content">{children}</div>
      </section>
    </div>
  );
}
