import { vision } from "@/lib/vision";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await request.text();
  const response = await vision(`/memories/${id}/active-hypothesis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  return Response.json(await response.json(), { status: response.status });
}
