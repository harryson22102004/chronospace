import { vision } from "@/lib/vision";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const response = await vision(`/memories/${id}`);
  const body = await response.json();
  return Response.json(body, { status: response.status });
}
