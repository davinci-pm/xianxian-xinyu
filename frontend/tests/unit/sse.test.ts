import { describe, expect, it } from "vitest";
import { parseSseBlock, readSse } from "@/lib/sse";

describe("SSE parser", () => {
  it("parses event and JSON data", () => {
    expect(parseSseBlock('event: chunk\ndata: {"text":"你好"}')).toEqual({
      event: "chunk",
      data: { text: "你好" },
    });
  });

  it("handles event boundaries split across network chunks", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: chunk\ndata: {"text":"先'));
        controller.enqueue(encoder.encode('贤"}\n\nevent: done\ndata: {"ok":true}\n\n'));
        controller.close();
      },
    });
    const events = [];
    for await (const event of readSse(new Response(stream))) events.push(event);
    expect(events).toEqual([
      { event: "chunk", data: { text: "先贤" } },
      { event: "done", data: { ok: true } },
    ]);
  });
});

