// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { applyMemoryOverlay, getNote, saveMemoryOverlay, saveNote, type NoteRecord } from "@/lib/local-data";
import type { MemoryItem } from "@/lib/types";

const storage = new Map<string, string>();
const storageMock = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => { storage.set(key, value); },
  removeItem: (key: string) => { storage.delete(key); },
  clear: () => storage.clear(),
  key: (index: number) => Array.from(storage.keys())[index] ?? null,
  get length() { return storage.size; },
};
Object.defineProperty(globalThis, "localStorage", { configurable: true, value: storageMock });

beforeEach(() => storageMock.clear());

describe("本机札记与记忆覆盖层", () => {
  it("离线时札记仍写入本机草稿", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    const now = new Date().toISOString();
    const note: NoteRecord = { id: "note-1", conversationId: "c-1", personaSlug: "confucius", personaName: "孔子", title: "原题", summary: "摘要", body: "离线草稿", themes: [], memories: [], createdAt: now, updatedAt: now };
    saveNote(note);
    expect(getNote("note-1")?.body).toBe("离线草稿");
  });

  it("支持暂停、修改展示与本机隐藏记忆", () => {
    const memory: MemoryItem = { id: "m-1", kind: "goal", content: "原内容", scope: "persona", status: "confirmed", confidence: 90, created_at: new Date().toISOString() };
    const overlays = saveMemoryOverlay({ memoryId: "m-1", content: "修改后", paused: true, hidden: true });
    expect(applyMemoryOverlay(memory, overlays)).toMatchObject({ content: "修改后", paused: true, hidden: true });
  });
});
