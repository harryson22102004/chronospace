/**
 * Meta Model API client.
 *
 * Base URL and model ids follow the public docs at https://dev.meta.ai/docs/models
 * A call is marked live only after HTTP success. This module never fabricates a response.
 */

import { parseImageStream, recordsOfKind, decodeMaskToRaster } from "@meta-sam/parser";

const BASE_URL = "https://api.meta.ai/v1";

export const MODELS = {
  spark: "muse-spark-1.3",
  image: "muse-image-1.0",
  sam: "sam-3.1",
  voice: "muse-voice-transcribe-1.0",
} as const;

export function modelApiKey(): string | null {
  const key = process.env.MODEL_API_KEY || process.env.META_API_KEY;
  return key && key.trim() ? key.trim() : null;
}

export type Invocation = {
  id: string;
  model_id: string;
  provider: "meta";
  task: string;
  status: "succeeded" | "failed";
  live: boolean;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  output_summary: string;
  error: string | null;
};

function nowIso() {
  return new Date().toISOString();
}

function invocationId() {
  return `inv_${Math.random().toString(16).slice(2, 12)}`;
}

async function metaFetch(path: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const key = modelApiKey();
  if (!key) throw new Error("MODEL_API_KEY is not set.");
  let last: Error | null = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const response = await fetch(`${BASE_URL}${path}`, {
        ...init,
        headers: {
          Authorization: `Bearer ${key}`,
          ...(init.headers || {}),
        },
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (response.status === 429 || response.status >= 500) {
        last = new Error(`Meta API ${response.status}`);
        await new Promise((resolve) => setTimeout(resolve, 400 * 2 ** attempt));
        continue;
      }
      return response;
    } catch (error) {
      last = error instanceof Error ? error : new Error(String(error));
      await new Promise((resolve) => setTimeout(resolve, 400 * 2 ** attempt));
    }
  }
  throw last || new Error("Meta API request failed.");
}

const AUDIO = new Set([
  "room tone",
  "wind",
  "distant birds",
  "clock",
  "fireplace",
  "rain",
  "crowd",
  "traffic",
]);

export function parseScenePlan(text: string): { title?: string; summary: string; audio: string[] } | null {
  const cleaned = text.trim().replace(/^```json\s*/i, "").replace(/```$/, "").trim();
  let data: unknown;
  try {
    data = JSON.parse(cleaned);
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const record = data as Record<string, unknown>;
  if (typeof record.summary !== "string" || record.summary.length < 8 || record.summary.length > 1800) {
    return null;
  }
  const title = typeof record.title === "string" ? record.title.slice(0, 90) : undefined;
  const audio = Array.isArray(record.audio)
    ? record.audio.filter((item): item is string => typeof item === "string" && AUDIO.has(item))
    : [];
  return { title, summary: record.summary, audio };
}

export async function museScenePlan(imageDataUrl: string, labels: string[]): Promise<{
  plan: { title?: string; summary: string; audio: string[] } | null;
  invocation: Invocation;
}> {
  const started = nowIso();
  const t0 = Date.now();
  const instructions =
    "You describe a photograph for a provenance-aware memory system. " +
    "Return JSON only with keys title, summary, audio. " +
    "summary is 2 sentences about what is visibly suggested. Do not invent a date, a measurement, or a hidden object. " +
    "audio is a subset of: room tone, wind, distant birds, clock, fireplace, rain, crowd, traffic.";
  try {
    const response = await metaFetch(
      "/responses",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODELS.spark,
          instructions,
          input: [
            {
              type: "message",
              role: "user",
              content: [
                {
                  type: "input_text",
                  text: `Local segmenter labels, which may be wrong: ${labels.join(", ") || "none"}. Describe only the photograph.`,
                },
                { type: "input_image", image_url: imageDataUrl },
              ],
            },
          ],
        }),
      },
      60_000,
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body?.error?.message || `Muse Spark HTTP ${response.status}`);
    }
    const text = extractOutputText(body);
    const plan = parseScenePlan(text);
    return {
      plan,
      invocation: {
        id: invocationId(),
        model_id: MODELS.spark,
        provider: "meta",
        task: "scene_description",
        status: plan ? "succeeded" : "failed",
        live: Boolean(plan),
        started_at: started,
        ended_at: nowIso(),
        duration_ms: Date.now() - t0,
        output_summary: plan ? plan.summary.slice(0, 280) : "The response was not valid scene JSON, so it was discarded.",
        error: plan ? null : "schema_rejected",
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Muse Spark failed.";
    return {
      plan: null,
      invocation: {
        id: invocationId(),
        model_id: MODELS.spark,
        provider: "meta",
        task: "scene_description",
        status: "failed",
        live: false,
        started_at: started,
        ended_at: nowIso(),
        duration_ms: Date.now() - t0,
        output_summary: message,
        error: message,
      },
    };
  }
}

type ToolCall = { name: string; args: Record<string, unknown> };

const TOOL_NAMES = new Set([
  "list_scene_entities",
  "get_entity_details",
  "get_entity_provenance",
  "get_scene_relationships",
  "focus_camera_on_entity",
  "highlight_object",
  "change_truth_lens_mode",
  "retrieve_user_memory",
  "add_memory_annotation",
  "create_alternative_hypothesis",
  "get_timeline_events",
]);

export async function museSelectTools(
  message: string,
  entityIndex: { id: string; label: string }[],
): Promise<{ calls: ToolCall[]; commentary: string | null; invocation: Invocation }> {
  const started = nowIso();
  const t0 = Date.now();
  const tools = [
    "list_scene_entities",
    "get_entity_details",
    "get_entity_provenance",
    "get_scene_relationships",
    "focus_camera_on_entity",
    "highlight_object",
    "change_truth_lens_mode",
    "retrieve_user_memory",
    "add_memory_annotation",
    "create_alternative_hypothesis",
    "get_timeline_events",
  ].map((name) => ({
    type: "function",
    name,
    description: `ChronoSpace tool ${name}. Arguments must match the scene index.`,
    parameters: { type: "object", additionalProperties: true },
  }));
  try {
    const response = await metaFetch(
      "/responses",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODELS.spark,
          instructions:
            "You are the Chronos spatial agent. Choose tools. Do not state facts that a tool did not return. " +
            "Never invent objects, dates, or distances. Entity ids must come from the index.",
          tools,
          input: `Scene index: ${JSON.stringify(entityIndex)}. User: ${message}`,
        }),
      },
      60_000,
    );
    const body = await response.json();
    if (!response.ok) throw new Error(body?.error?.message || `Muse Spark HTTP ${response.status}`);
    const calls = extractToolCalls(body).filter((call) => TOOL_NAMES.has(call.name)).slice(0, 6);
    const commentary = extractOutputText(body);
    return {
      calls,
      commentary: commentary || null,
      invocation: {
        id: invocationId(),
        model_id: MODELS.spark,
        provider: "meta",
        task: "spatial_agent",
        status: "succeeded",
        live: true,
        started_at: started,
        ended_at: nowIso(),
        duration_ms: Date.now() - t0,
        output_summary: calls.length
          ? `Selected ${calls.map((call) => call.name).join(", ")}.`
          : "Completed with no tool call.",
        error: null,
      },
    };
  } catch (error) {
    const messageText = error instanceof Error ? error.message : "Muse Spark failed.";
    return {
      calls: [],
      commentary: null,
      invocation: {
        id: invocationId(),
        model_id: MODELS.spark,
        provider: "meta",
        task: "spatial_agent",
        status: "failed",
        live: false,
        started_at: started,
        ended_at: nowIso(),
        duration_ms: Date.now() - t0,
        output_summary: messageText,
        error: messageText,
      },
    };
  }
}

export async function segmentWithSam(imageDataUrl: string, prompt: string, frameWidth: number, frameHeight: number) {
  const started = nowIso();
  const t0 = Date.now();
  const response = await metaFetch(
    "/responses",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: MODELS.sam,
        stream: true,
        metadata: { mask_encoding: "one_bit", include_confidence: "true" },
        input: [
          {
            type: "message",
            role: "user",
            content: [
              { type: "input_text", text: prompt },
              { type: "input_image", image_url: imageDataUrl },
            ],
          },
        ],
      }),
    },
    90_000,
  );
  if (!response.ok || !response.body) {
    const detail = await response.text();
    const invocation: Invocation = {
      id: invocationId(),
      model_id: MODELS.sam,
      provider: "meta",
      task: `segment:${prompt}`,
      status: "failed",
      live: false,
      started_at: started,
      ended_at: nowIso(),
      duration_ms: Date.now() - t0,
      output_summary: detail.slice(0, 300),
      error: `HTTP ${response.status}`,
    };
    return { masks: [], invocation };
  }
  const parsed = await parseImageStream(sseEvents(response)).finalResult;
  const masks = [];
  for (const record of recordsOfKind(parsed.records, "mask")) {
    const raster = decodeMaskToRaster(record.mask);
    const full = new Uint8Array(frameWidth * frameHeight);
    for (let y = 0; y < record.mask.height; y++) {
      for (let x = 0; x < record.mask.width; x++) {
        if (raster[y * record.mask.width + x] !== 1) continue;
        const px = record.bounds.left + x;
        const py = record.bounds.top + y;
        if (px < 0 || py < 0 || px >= frameWidth || py >= frameHeight) continue;
        full[py * frameWidth + px] = 255;
      }
    }
    masks.push({
      objectId: record.objectId,
      confidence: typeof record.confidence === "number" ? record.confidence : null,
      pngReadyRaw: Buffer.from(full).toString("base64"),
    });
  }
  const invocation: Invocation = {
    id: invocationId(),
    model_id: MODELS.sam,
    provider: "meta",
    task: `segment:${prompt}`,
    status: "succeeded",
    live: true,
    started_at: started,
    ended_at: nowIso(),
    duration_ms: Date.now() - t0,
    output_summary: masks.length
      ? `SAM 3.1 returned ${masks.length} mask(s) for “${prompt}”.`
      : `SAM 3.1 returned no match for “${prompt}”.`,
    error: null,
  };
  return { masks, invocation };
}

export async function museImageHypothesis(imageDataUrl: string, claim: string) {
  const started = nowIso();
  const t0 = Date.now();
  try {
    const response = await metaFetch(
      "/responses",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODELS.image,
          input: [
            {
              type: "message",
              role: "user",
              content: [
                {
                  type: "input_text",
                  text:
                    `Hypothetical illustration only. Depict this recollection inside the dark unobserved area and leave the rest of the photograph unchanged: ${claim}. ` +
                    "Do not present the result as a restored fact.",
                },
                { type: "input_image", image_url: imageDataUrl },
              ],
            },
          ],
        }),
      },
      120_000,
    );
    const body = await response.json();
    if (!response.ok) throw new Error(body?.error?.message || `Muse Image HTTP ${response.status}`);
    const image = extractGeneratedImage(body);
    if (!image) throw new Error("Muse Image returned no image_generation_call.");
    return {
      bytes: Buffer.from(image, "base64"),
      invocation: {
        id: invocationId(),
        model_id: MODELS.image,
        provider: "meta" as const,
        task: "image_hypothesis",
        status: "succeeded" as const,
        live: true,
        started_at: started,
        ended_at: nowIso(),
        duration_ms: Date.now() - t0,
        output_summary: "Muse Image returned an image. Only the unobserved mask will be kept.",
        error: null,
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Muse Image failed.";
    return {
      bytes: null,
      invocation: {
        id: invocationId(),
        model_id: MODELS.image,
        provider: "meta" as const,
        task: "image_hypothesis",
        status: "failed" as const,
        live: false,
        started_at: started,
        ended_at: nowIso(),
        duration_ms: Date.now() - t0,
        output_summary: message,
        error: message,
      },
    };
  }
}

export async function transcribeWav(wav: Buffer) {
  const started = nowIso();
  const t0 = Date.now();
  const key = modelApiKey();
  if (!key) throw new Error("MODEL_API_KEY is not set.");
  const form = new FormData();
  form.set(
    "request",
    new Blob(
      [JSON.stringify({ model: MODELS.voice, audioEncoding: "WAV", mode: "PUSH_TO_TALK", languageBias: ["English"] })],
      { type: "application/json" },
    ),
  );
  form.set("audio", new Blob([new Uint8Array(wav)], { type: "audio/wav" }), "recollection.wav");
  const response = await fetch(`${BASE_URL}/asr/transcribe`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, Accept: "application/json" },
    body: form,
    signal: AbortSignal.timeout(60_000),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || typeof body.transcript !== "string") {
    return {
      transcript: null as string | null,
      invocation: {
        id: invocationId(),
        model_id: MODELS.voice,
        provider: "meta" as const,
        task: "transcription",
        status: "failed" as const,
        live: false,
        started_at: started,
        ended_at: nowIso(),
        duration_ms: Date.now() - t0,
        output_summary: body?.error?.message || `Transcription HTTP ${response.status}`,
        error: body?.error?.message || `HTTP ${response.status}`,
      },
    };
  }
  return {
    transcript: body.transcript as string,
    invocation: {
      id: invocationId(),
      model_id: MODELS.voice,
      provider: "meta" as const,
      task: "transcription",
      status: "succeeded" as const,
      live: true,
      started_at: started,
      ended_at: nowIso(),
      duration_ms: Date.now() - t0,
      output_summary: `Transcript of ${body.audioDurationMs ?? "unknown"} ms. Awaiting confirmation before it becomes testimony.`,
      error: null,
    },
  };
}

function extractOutputText(body: { output?: Array<Record<string, unknown>> }): string {
  const parts: string[] = [];
  for (const item of body.output || []) {
    if (item.type !== "message") continue;
    const content = item.content;
    if (!Array.isArray(content)) continue;
    for (const part of content) {
      if (part && typeof part === "object" && "text" in part && typeof part.text === "string") {
        parts.push(part.text);
      }
    }
  }
  return parts.join("\n").trim();
}

function extractToolCalls(body: { output?: Array<Record<string, unknown>> }): ToolCall[] {
  const calls: ToolCall[] = [];
  for (const item of body.output || []) {
    if (item.type !== "function_call" || typeof item.name !== "string") continue;
    let args: Record<string, unknown> = {};
    if (typeof item.arguments === "string") {
      try {
        const parsed = JSON.parse(item.arguments);
        if (parsed && typeof parsed === "object") args = parsed as Record<string, unknown>;
      } catch {
        continue;
      }
    }
    calls.push({ name: item.name, args });
  }
  return calls;
}

function extractGeneratedImage(body: { output?: Array<Record<string, unknown>> }): string | null {
  for (const item of body.output || []) {
    if (item.type === "image_generation_call" && typeof item.result === "string") return item.result;
  }
  return null;
}

async function* sseEvents(response: Response): AsyncGenerator<{ type: string; [key: string]: unknown }> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("");
      if (!data || data === "[DONE]") continue;
      const json = JSON.parse(data);
      if (json && typeof json.type === "string") yield json;
    }
  }
}
