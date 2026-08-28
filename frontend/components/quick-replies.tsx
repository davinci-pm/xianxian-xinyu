"use client";

export default function QuickReplies({ replies, onChoose }: { replies: string[]; onChoose: (reply: string) => void }) {
  if (!replies.length) return null;
  return <div className="quick-replies" aria-label="快捷回答">{replies.map((reply) => <button type="button" key={reply} onClick={() => onChoose(reply)}>{reply}</button>)}</div>;
}

