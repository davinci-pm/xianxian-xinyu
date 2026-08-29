// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { getNote, saveNote, type NoteRecord } from "@/lib/local-data";

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

describe("本机札记", () => {
  it("离线时札记仍写入本机草稿", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
    const now = new Date().toISOString();
    const note: NoteRecord = { id: "note-1", conversationId: "c-1", personaSlug: "confucius", personaName: "孔子", title: "原题", summary: "摘要", body: "离线草稿", themes: [], memories: [], createdAt: now, updatedAt: now };
    saveNote(note);
    expect(getNote("note-1")?.body).toBe("离线草稿");
  });
});
