import { modelApiKey, transcribeWav } from "@/lib/meta";

export async function POST(request: Request) {
  if (!modelApiKey()) {
    return Response.json(
      {
        transcript: null,
        message: "Voice transcription needs MODEL_API_KEY and a 16 kHz mono WAV. Nothing was invented in its place.",
      },
      { status: 409 },
    );
  }
  const form = await request.formData();
  const audio = form.get("audio");
  if (!(audio instanceof File)) return Response.json({ message: "Attach a WAV file." }, { status: 400 });
  const wav = Buffer.from(await audio.arrayBuffer());
  const result = await transcribeWav(wav);
  if (!result.transcript) {
    return Response.json({ transcript: null, invocation: result.invocation, message: result.invocation.error }, { status: 502 });
  }
  return Response.json({ transcript: result.transcript, invocation: result.invocation });
}
