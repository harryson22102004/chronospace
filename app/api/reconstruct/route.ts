import fs from "fs";
import path from "path";
import { modelApiKey, museScenePlan, segmentWithSam } from "@/lib/meta";
import { VISION_URL } from "@/lib/vision";

export const runtime = "nodejs";

const encoder = new TextEncoder();

function frame(payload: unknown) {
  return encoder.encode(`data: ${JSON.stringify(payload)}\n\n`);
}

export async function POST(request: Request) {
  const incoming = await request.formData();
  const upstream = await fetch(`${VISION_URL}/reconstruct`, { method: "POST", body: incoming });
  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return Response.json({ message: text || "The vision service rejected the photograph." }, { status: upstream.status || 502 });
  }
  const reader = upstream.body.getReader();
  const stream = new ReadableStream({
    async start(controller) {
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() || "";
          for (const block of blocks) {
            const line = block
              .split("\n")
              .filter((item) => item.startsWith("data:"))
              .map((item) => item.slice(5).trim())
              .join("");
            if (!line) continue;
            const payload = JSON.parse(line);
            if (payload.event === "done" && payload.memory) {
              const enriched = await enrich(payload.memory, controller);
              controller.enqueue(frame({ event: "done", memory: enriched }));
            } else {
              controller.enqueue(frame(payload));
            }
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Reconstruction stream failed.";
        controller.enqueue(frame({ event: "error", message }));
      } finally {
        controller.close();
      }
    },
  });
  return new Response(stream, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
  });
}

async function enrich(memory: { id: string; consent?: { external_models?: boolean }; entities: { label: string }[]; photograph: { url: string; width: number; height: number } }, controller: ReadableStreamDefaultController) {
  if (!memory.consent?.external_models || !modelApiKey()) return memory;
  const file = path.join(process.cwd(), "data", memory.photograph.url);
  if (!fs.existsSync(file)) return memory;
  const dataUrl = `data:image/jpeg;base64,${fs.readFileSync(file).toString("base64")}`;
  const labels = [...new Set(memory.entities.map((entity) => entity.label))].filter(
    (label) => !["wall", "floor", "region"].includes(label),
  );
  controller.enqueue(frame({ event: "stage", stage: "object_segmentation", status: "running", detail: "Calling SAM 3.1 for named regions." }));
  for (const prompt of labels.slice(0, 4)) {
    const sam = await segmentWithSam(dataUrl, prompt, memory.photograph.width, memory.photograph.height);
    for (const mask of sam.masks) {
      await fetch(`${VISION_URL}/memories/${memory.id}/sam`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          object_id: mask.objectId,
          width: memory.photograph.width,
          height: memory.photograph.height,
          mask_raw_base64: mask.pngReadyRaw,
          confidence: mask.confidence,
          invocation: sam.invocation,
        }),
      });
    }
    if (!sam.masks.length) {
      await fetch(`${VISION_URL}/memories/${memory.id}/invocations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ invocation: sam.invocation }),
      });
    }
  }
  controller.enqueue(
    frame({
      event: "stage",
      stage: "object_segmentation",
      status: "succeeded",
      detail: "SAM 3.1 finished. Empty matches stay empty.",
    }),
  );
  controller.enqueue(frame({ event: "stage", stage: "semantic_reconstruction", status: "running", detail: "Asking Muse Spark for a scene description." }));
  const scene = await museScenePlan(dataUrl, labels);
  if (scene.plan) {
    await fetch(`${VISION_URL}/memories/${memory.id}/scene`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: scene.plan.title,
        summary: scene.plan.summary,
        audio_elements: scene.plan.audio,
        invocation: scene.invocation,
      }),
    });
  } else {
    await fetch(`${VISION_URL}/memories/${memory.id}/invocations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invocation: scene.invocation }),
    });
  }
  controller.enqueue(
    frame({
      event: "stage",
      stage: "semantic_reconstruction",
      status: scene.plan ? "succeeded" : "failed",
      detail: scene.invocation.output_summary,
    }),
  );
  const fresh = await fetch(`${VISION_URL}/memories/${memory.id}`);
  if (!fresh.ok) return memory;
  return fresh.json();
}
