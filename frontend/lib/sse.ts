// SSE parser over a fetch ReadableStream. The backend emits event-source
// frames in the form:
//
//   event: token
//   data: {"content": "Hello"}
//
//   event: done
//   data: {}
//
// We can't use EventSource because it's GET-only and we need to send the
// JWT in an Authorization header.

export type SseEvent = {
  event: string;
  data: unknown;
};

export async function* streamSse(
  response: Response,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
  if (!response.body) throw new Error("Response has no body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        return;
      }
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Frames are separated by a blank line. They can use \r\n on Windows
      // or \n on Unix; handle both.
      let sep: number;
      while ((sep = findFrameEnd(buffer)) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep).replace(/^(\r?\n)+/, "");
        const parsed = parseFrame(frame);
        if (parsed) yield parsed;
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* noop */
    }
  }
}

function findFrameEnd(s: string): number {
  const a = s.indexOf("\n\n");
  const b = s.indexOf("\r\n\r\n");
  if (a === -1) return b;
  if (b === -1) return a;
  return Math.min(a, b);
}

function parseFrame(frame: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (!line) continue;
    if (line.startsWith(":")) continue; // comment
    const idx = line.indexOf(":");
    if (idx === -1) continue;
    const field = line.slice(0, idx);
    const val = line.slice(idx + 1).replace(/^ /, "");
    if (field === "event") event = val;
    else if (field === "data") dataLines.push(val);
  }
  if (dataLines.length === 0) return null;
  const raw = dataLines.join("\n");
  let data: unknown = raw;
  try {
    data = JSON.parse(raw);
  } catch {
    /* keep raw string */
  }
  return { event, data };
}
