import { vision } from "@/lib/vision";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await request.json();
  const response = await vision(`/memories/${id}/testimony`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: body.text,
      speaker: body.speaker || null,
      source: body.source || "typed",
      transcript_model: body.transcript_model || null,
    }),
  });
  return Response.json(await response.json(), { status: response.status });
}
