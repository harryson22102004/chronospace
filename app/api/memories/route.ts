import { vision } from "@/lib/vision";

export async function GET() {
  const response = await vision("/memories");
  if (!response.ok) {
    return Response.json({ memories: [], error: "Vision service is not running." }, { status: 200 });
  }
  return Response.json(await response.json());
}
