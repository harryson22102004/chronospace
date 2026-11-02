import { museSelectTools, modelApiKey } from "@/lib/meta";
import { vision } from "@/lib/vision";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const { message } = (await request.json()) as { message?: string };
  if (!message?.trim()) return Response.json({ narration: "Say something about this memory." }, { status: 400 });
  const memoryResponse = await vision(`/memories/${id}`);
  if (!memoryResponse.ok) return Response.json({ narration: "Memory not found." }, { status: 404 });
  const memory = await memoryResponse.json();
  const key = modelApiKey();
  if (key && memory.consent?.external_models) {
    const selected = await museSelectTools(
      message,
      memory.entities.map((entity: { id: string; label: string }) => ({ id: entity.id, label: entity.label })),
    );
    await vision(`/memories/${id}/invocations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invocation: selected.invocation }),
    });
    if (selected.invocation.live && selected.calls.length) {
      const trace = [];
      const actions = [];
      for (const call of selected.calls) {
        const toolResponse = await vision(`/agent/tool?memory_id=${id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: call.name, args: call.args }),
        });
        const tool = await toolResponse.json();
        trace.push({ name: call.name, args: call.args, result: tool.result });
        actions.push(...(tool.actions || []));
      }
      const summary = await vision("/agent/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trace }),
      });
      const narration = (await summary.json()).narration as string;
      return Response.json({
        narration,
        commentary: selected.commentary,
        tool_trace: trace,
        actions,
        source: { model_id: "muse-spark-1.3", provider: "meta", live: true },
      });
    }
  }
  const local = await vision(`/agent/turn?memory_id=${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return Response.json(await local.json(), { status: local.status });
}
