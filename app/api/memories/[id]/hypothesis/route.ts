import fs from "fs";
import path from "path";
import { museImageHypothesis, modelApiKey } from "@/lib/meta";
import { vision } from "@/lib/vision";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = (await request.json()) as { claim?: string; speaker?: string };
  if (!body.claim?.trim()) return Response.json({ message: "A hypothesis needs a claim." }, { status: 400 });
  const memoryResponse = await vision(`/memories/${id}`);
  if (!memoryResponse.ok) return Response.json({ message: "Memory not found." }, { status: 404 });
  const memory = await memoryResponse.json();
  const unknown = memory.entities?.some((entity: { content_status: string }) => entity.content_status === "unknown");
  if (modelApiKey() && memory.consent?.external_models && unknown) {
    const file = path.join(process.cwd(), "data", memory.photograph.url);
    const dataUrl = `data:image/jpeg;base64,${fs.readFileSync(file).toString("base64")}`;
    const generated = await museImageHypothesis(dataUrl, body.claim);
    await vision(`/memories/${id}/invocations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invocation: generated.invocation }),
    });
    if (generated.bytes && generated.invocation.live) {
      const form = new FormData();
      form.set("claim", body.claim);
      form.set("model_id", "muse-image-1.0");
      form.set("live", "true");
      form.set("file", new Blob([new Uint8Array(generated.bytes)], { type: "image/png" }), "hypothesis.png");
      const response = await vision(`/memories/${id}/hypothesis/external`, { method: "POST", body: form });
      const payload = await response.json();
      return Response.json(payload, { status: response.status });
    }
  }
  const response = await vision(`/memories/${id}/hypothesis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim: body.claim, speaker: body.speaker || null }),
  });
  const payload = await response.json();
  if (!response.ok) return Response.json(payload, { status: response.status });
  if (payload.result && payload.result.created === false) {
    return Response.json({ message: payload.result.reason }, { status: 400 });
  }
  return Response.json(payload);
}
