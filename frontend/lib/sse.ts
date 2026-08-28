import type { StreamEvent } from "@/lib/types";

export function parseSseBlock(block: string): StreamEvent | null {
  const lines = block.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (!eventLine || dataLines.length === 0) return null;
  const event = eventLine.slice(6).trim() as StreamEvent["event"];
  const rawData = dataLines.map((line) => line.slice(5).trim()).join("\n");
  return { event, data: JSON.parse(rawData) as Record<string, unknown> };
}

export async function* readSse(response: Response): AsyncGenerator<StreamEvent> {
  if (!response.ok || !response.body) throw new Error(`流式请求失败：${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const parsed = parseSseBlock(block);
      if (parsed) yield parsed;
    }
    if (done) break;
  }
  if (buffer.trim()) {
    const parsed = parseSseBlock(buffer);
    if (parsed) yield parsed;
  }
}

