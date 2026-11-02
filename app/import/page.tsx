"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";

const STAGES = [
  ["photograph_analysis", "Photograph analysis"],
  ["object_segmentation", "Object segmentation"],
  ["depth_estimation", "Depth estimation"],
  ["semantic_reconstruction", "Semantic reconstruction"],
  ["generative_completion", "Generative completion"],
  ["evidence_graph", "Evidence graph"],
  ["spatial_rendering", "Spatial rendering"],
] as const;

type StageState = { status: string; detail: string };

export default function ImportPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState(false);
  const [external, setExternal] = useState(false);
  const [exif, setExif] = useState(false);
  const [note, setNote] = useState("");
  const [stages, setStages] = useState<Record<string, StageState>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  async function submit() {
    if (!file || !rights) return;
    setBusy(true);
    setError(null);
    setStages({});
    const form = new FormData();
    form.set("file", file);
    form.set("rights_confirmed", "true");
    form.set("external_models", external ? "true" : "false");
    form.set("use_capture_time", exif ? "true" : "false");
    form.set("note", note);
    try {
      const response = await fetch("/api/reconstruct", { method: "POST", body: form });
      if (!response.ok || !response.body) {
        const body = await response.json().catch(() => ({}));
        setError(body.message || "The photograph could not be reconstructed.");
        setBusy(false);
        return;
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
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
          if (payload.event === "stage") {
            setStages((current) => ({
              ...current,
              [payload.stage]: { status: payload.status, detail: payload.detail },
            }));
          }
          if (payload.event === "error") setError(payload.message);
          if (payload.event === "done" && payload.memory?.id) {
            if (transcript) {
              await fetch(`/api/memories/${payload.memory.id}/testimony`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: transcript, source: "voice_transcript_confirmed" }),
              }).catch(() => undefined);
            }
            router.push(`/memory/${payload.memory.id}`);
          }
        }
      }
    } catch {
      setError("The reconstruction request did not finish.");
    } finally {
      setBusy(false);
    }
  }

  async function onVoice(file: File) {
    setVoiceError(null);
    const wav = await encodeWav(file);
    const form = new FormData();
    form.set("audio", wav, "recollection.wav");
    const response = await fetch("/api/voice", { method: "POST", body: form });
    const body = await response.json();
    if (!response.ok || !body.transcript) {
      setVoiceError(body.message || "Transcription did not return text.");
      return;
    }
    setTranscript(body.transcript);
  }

  return (
    <main className="mx-auto grid max-w-5xl gap-6 px-4 py-8 md:grid-cols-2">
      <section>
        <p className="kicker">Memory import</p>
        <h1 className="serif mt-2 text-4xl">Bring an ordinary photograph.</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
          Local depth and segmentation run on this machine. Meta models run only if you consent and a server-side key is configured.
          Nothing here pretends a skipped call succeeded.
        </p>
        <label className="glass mt-6 block cursor-pointer rounded-3xl p-6 text-sm">
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          {file ? file.name : "Choose a JPEG, PNG, or WebP under 12 MB"}
        </label>
        <label className="mt-4 flex gap-3 text-sm">
          <input type="checkbox" checked={rights} onChange={(event) => setRights(event.target.checked)} />
          I have the right to process this photograph.
        </label>
        <label className="mt-2 flex gap-3 text-sm">
          <input type="checkbox" checked={external} onChange={(event) => setExternal(event.target.checked)} />
          Send it to Meta’s model API for segmentation, description, and optional image hypotheses.
        </label>
        <label className="mt-2 flex gap-3 text-sm">
          <input type="checkbox" checked={exif} onChange={(event) => setExif(event.target.checked)} />
          Read a capture time from EXIF before the metadata is removed.
        </label>
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Optional note. This stays testimony or context, not a fact about the pixels."
          className="mt-4 h-24 w-full rounded-2xl border border-[var(--line)] bg-black/30 p-3 text-sm outline-none"
        />
        <div className="mt-4">
          <p className="text-sm">Voice recollection</p>
          <input
            type="file"
            accept="audio/*"
            className="mt-2 text-sm"
            onChange={(event) => {
              const audio = event.target.files?.[0];
              if (audio) void onVoice(audio);
            }}
          />
          <p className="mt-1 text-xs text-[var(--muted)]">
            The clip is converted in the browser to 16 kHz mono WAV. A transcript becomes testimony only after you leave it in the box and import.
          </p>
          {transcript && (
            <textarea
              value={transcript}
              onChange={(event) => setTranscript(event.target.value)}
              className="mt-2 h-20 w-full rounded-2xl border border-[var(--line)] bg-black/30 p-3 text-sm"
            />
          )}
          {voiceError && <p className="mt-2 text-sm text-[var(--amber)]">{voiceError}</p>}
        </div>
        <Button className="mt-5" variant="gold" disabled={!file || !rights || busy} onClick={() => void submit()}>
          {busy ? "Reconstructing" : "Reconstruct"}
        </Button>
        {error && <p className="mt-3 text-sm text-[var(--danger)]">{error}</p>}
      </section>
      <section className="glass rounded-3xl p-5">
        <p className="kicker">Processing</p>
        <ol className="mt-4 space-y-4">
          {STAGES.map(([id, label]) => {
            const stage = stages[id];
            return (
              <li key={id}>
                <div className="flex items-center justify-between text-sm">
                  <span>{label}</span>
                  <span className="text-[var(--gold)]">{stage?.status || "waiting"}</span>
                </div>
                <p className="mt-1 text-xs text-[var(--muted)]">{stage?.detail || "Not started."}</p>
              </li>
            );
          })}
        </ol>
      </section>
    </main>
  );
}

async function encodeWav(file: File) {
  const ctx = new AudioContext();
  const decoded = await ctx.decodeAudioData(await file.arrayBuffer());
  const length = Math.max(1, Math.ceil(decoded.duration * 16000));
  const offline = new OfflineAudioContext(1, length, 16000);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const rendered = await offline.startRendering();
  await ctx.close();
  const samples = rendered.getChannelData(0);
  const pcm = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  const write = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + pcm.byteLength, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true);
  view.setUint32(28, 16000 * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, pcm.byteLength, true);
  return new Blob([header, pcm], { type: "audio/wav" });
}
