"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { LivingScene, type LensMode } from "@/components/living-scene";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { useAmbience } from "@/components/ambience";
import { fileUrl } from "@/lib/utils";
import type { AgentTurn, Entity, Memory, Provenance } from "@/lib/types";

const LENSES: { id: LensMode; label: string; hint: string }[] = [
  { id: "original", label: "Original", hint: "The photograph, flat." },
  { id: "observed", label: "Observed", hint: "Source pixels. Generated areas drop out." },
  { id: "inferred", label: "Inferred", hint: "Relative depth, in blue." },
  { id: "generated", label: "Generated", hint: "Violet marks pixels we created." },
  { id: "testimony", label: "Testimony", hint: "Amber marks what a person said." },
  { id: "all", label: "All evidence", hint: "The reconstruction with every class visible." },
];

export function MemoryStudio({ id, view }: { id: string; view: "living" | "audit" | "graph" | "realities" }) {
  const [memory, setMemory] = useState<Memory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lens, setLens] = useState<LensMode>("all");
  const [depthAmount, setDepthAmount] = useState(0.72);
  const [motionOn, setMotionOn] = useState(true);
  const [soundOn, setSoundOn] = useState(false);
  const [volume, setVolume] = useState(0.4);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [highlight, setHighlight] = useState<[number, number] | null>(null);
  const [question, setQuestion] = useState("Show me the old record player.");
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [asking, setAsking] = useState(false);
  const [offer, setOffer] = useState<string | null>(null);

  async function refresh() {
    const response = await fetch(`/api/memories/${id}`, { cache: "no-store" });
    if (!response.ok) {
      setError("This memory is not on the vision service.");
      return;
    }
    const next = (await response.json()) as Memory;
    setMemory(next);
    setError(null);
  }

  useEffect(() => {
    void refresh();
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (motion.matches) setMotionOn(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useAmbience(memory?.audio_profile.elements || [], soundOn, volume);

  const hypothesis = useMemo(() => {
    if (!memory?.active_hypothesis_id) return null;
    return memory.hypotheses.find((item) => item.id === memory.active_hypothesis_id) || null;
  }, [memory]);

  function applyActions(turn: AgentTurn) {
    if (!memory) return;
    for (const action of turn.actions) {
      if ((action.type === "focus_camera" || action.type === "highlight") && action.entity_id) {
        const entity = memory.entities.find((item) => item.id === action.entity_id) || null;
        setSelected(entity);
        if (action.uv) setHighlight(action.uv);
      }
      if (action.type === "truth_lens" && action.mode) setLens(action.mode as LensMode);
      if (action.type === "offer_hypothesis" && action.claim) setOffer(action.claim);
      if (action.type === "show_hypothesis") void refresh();
    }
  }

  async function ask(text: string) {
    if (!text.trim()) return;
    setAsking(true);
    setOffer(null);
    try {
      const response = await fetch(`/api/memories/${id}/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const turn = (await response.json()) as AgentTurn;
      setTurns((current) => [...current, turn]);
      applyActions(turn);
      if (turn.actions.some((action) => action.type === "show_testimony" || action.type === "show_hypothesis")) {
        await refresh();
      }
    } catch {
      setError("The agent could not reach the vision service.");
    } finally {
      setAsking(false);
    }
  }

  async function createHypothesis(claim: string) {
    setAsking(true);
    try {
      const response = await fetch(`/api/memories/${id}/hypothesis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(body.detail || body.message || "The hypothesis was not created.");
        return;
      }
      setLens("generated");
      setOffer(null);
      await refresh();
    } finally {
      setAsking(false);
    }
  }

  async function chooseHypothesis(hypothesisId: string | null) {
    await fetch(`/api/memories/${id}/active-hypothesis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hypothesis_id: hypothesisId }),
    });
    if (hypothesisId) setLens("generated");
    await refresh();
  }

  if (error && !memory) {
    return <p className="px-8 py-16 text-[var(--danger)]">{error}</p>;
  }
  if (!memory) {
    return <p className="px-8 py-16 text-[var(--muted)]">Reading the memory record…</p>;
  }

  const liveMeta = memory.invocations.some((item) => item.live && item.status === "succeeded" && item.provider === "meta");

  return (
    <div className="grid min-h-[calc(100vh-64px)] grid-rows-[auto_1fr] px-3 pb-6 md:px-6">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="kicker">{memory.sample ? "Painted reference" : "Memory"}</p>
          <h1 className="serif text-3xl md:text-4xl">{memory.title}</h1>
          {memory.sample_note && <p className="mt-1 max-w-2xl text-sm text-[var(--muted)]">{memory.sample_note}</p>}
        </div>
        <nav className="flex flex-wrap gap-2 text-sm">
          <Tab href={`/memory/${id}`} active={view === "living"}>Living memory</Tab>
          <Tab href={`/memory/${id}/audit`} active={view === "audit"}>Epistemic audit</Tab>
          <Tab href={`/memory/${id}/graph`} active={view === "graph"}>ChronosGraph</Tab>
          <Tab href={`/memory/${id}/realities`} active={view === "realities"}>Realities</Tab>
        </nav>
      </div>

      {view === "living" && (
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section className="glass relative overflow-hidden rounded-3xl">
            <LivingScene
              width={memory.photograph.width}
              height={memory.photograph.height}
              photo={fileUrl(memory.photograph.url)}
              depth={fileUrl(memory.assets.depth)}
              entityIds={fileUrl(memory.assets.entity_ids)}
              unknown={fileUrl(memory.assets.unknown)}
              generated={fileUrl(memory.assets.generated)}
              testimony={fileUrl(memory.assets.testimony)}
              motion={fileUrl(memory.assets.motion)}
              hypothesis={hypothesis ? fileUrl(hypothesis.artifact_url) : null}
              lens={lens}
              depthAmount={depthAmount}
              motionOn={motionOn}
              highlightUv={highlight}
              onSelectIndex={(index) => {
                const entity = memory.entities.find((item) => item.index === index) || null;
                setSelected(entity);
                if (entity) setHighlight(entity.centroid_uv);
              }}
            />
            <div className="absolute left-3 right-3 top-3 flex flex-wrap gap-1.5">
              {LENSES.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setLens(item.id)}
                  className={`rounded-full px-3 py-1 text-xs ${lens === item.id ? "bg-[var(--ink)] text-[#1a1612]" : "bg-black/45 text-[var(--ink)]"}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </section>
          <aside className="flex max-h-[78vh] flex-col gap-3 overflow-auto">
            <div className="glass rounded-3xl p-4">
              <p className="kicker">Truth lens</p>
              <p className="mt-2 text-sm text-[var(--muted)]">{LENSES.find((item) => item.id === lens)?.hint}</p>
              <div className="mt-4">
                <Slider label="Depth displacement" value={depthAmount} onValueChange={setDepthAmount} />
              </div>
              <div className="mt-4 space-y-3">
                <Switch checked={motionOn} onCheckedChange={setMotionOn} label="Region motion" />
                <Switch checked={soundOn} onCheckedChange={setSoundOn} label="Sound bed" />
                {soundOn && <Slider label="Level" value={volume} onValueChange={setVolume} />}
              </div>
              <p className="mt-3 text-xs text-[var(--muted)]">{memory.audio_profile.note}</p>
            </div>
            <ProvenanceCard memory={memory} entity={selected} />
            <div className="glass rounded-3xl p-4">
              <p className="kicker">Chronos agent</p>
              <p className="mt-1 text-xs text-[var(--muted)]">
                {liveMeta ? "A live Meta call has succeeded on this memory." : "No live Meta call yet. Answers come from the scene graph."}
              </p>
              <div className="mt-3 space-y-3">
                {turns.map((turn, index) => (
                  <article key={index} className="rounded-2xl bg-black/25 p-3 text-sm">
                    <p>{turn.narration}</p>
                    <p className="mt-2 text-[11px] uppercase tracking-wider text-[var(--gold)]">
                      {turn.source.model_id}
                      {turn.source.live ? " · live" : " · local"}
                    </p>
                    <ul className="mt-1 text-xs text-[var(--muted)]">
                      {turn.tool_trace.map((tool, toolIndex) => (
                        <li key={toolIndex}>{tool.name}</li>
                      ))}
                    </ul>
                    {turn.commentary && (
                      <p className="mt-2 text-xs text-[var(--muted)]">Model commentary, not verified: {turn.commentary}</p>
                    )}
                  </article>
                ))}
              </div>
              {offer && (
                <Button className="mt-3 w-full" variant="gold" onClick={() => createHypothesis(offer)} disabled={asking}>
                  Sketch this as a hypothesis
                </Button>
              )}
              <form
                className="mt-3 flex gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  void ask(question);
                }}
              >
                <input
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  className="w-full rounded-full border border-[var(--line)] bg-black/30 px-3 py-2 text-sm outline-none"
                />
                <Button type="submit" disabled={asking}>
                  Ask
                </Button>
              </form>
            </div>
          </aside>
        </div>
      )}

      {view === "audit" && <Audit memory={memory} onSelect={setSelected} selected={selected} />}
      {view === "graph" && <Graph memory={memory} />}
      {view === "realities" && (
        <Realities memory={memory} onCreate={createHypothesis} onChoose={chooseHypothesis} busy={asking} />
      )}
      {error && <p className="mt-3 text-sm text-[var(--danger)]">{error}</p>}
    </div>
  );
}

function Tab({ href, active, children }: { href: string; active: boolean; children: ReactNode }) {
  return (
    <Link
      href={href}
      className={`rounded-full px-3 py-1 ${active ? "bg-[var(--ink)] text-[#1a1612]" : "border border-[var(--line)] text-[var(--muted)]"}`}
    >
      {children}
    </Link>
  );
}

function ProvenanceCard({ memory, entity }: { memory: Memory; entity: Entity | null }) {
  if (!entity) {
    return (
      <div className="glass rounded-3xl p-4 text-sm text-[var(--muted)]">
        Select a region in the photograph. Its pixels, mask, and depth stay attached to the record.
      </div>
    );
  }
  const records = memory.provenances.filter((item) => item.entity_id === entity.id);
  return (
    <div className="glass rounded-3xl p-4">
      <p className="kicker">Lineage</p>
      <h2 className="serif mt-1 text-2xl capitalize">{entity.label}</h2>
      <p className="mt-2 text-sm text-[var(--muted)]">{entity.classifier_note}</p>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <Fact label="Content" value={entity.content_status} />
        <Fact label="Label from" value={entity.label_origin} />
        <Fact label="Relative depth" value={entity.median_disparity?.toFixed(3) ?? "—"} />
        <Fact label="Calibration" value={memory.depth.calibration_status} />
      </dl>
      {entity.model_native_confidence && (
        <p className="mt-2 text-xs text-[var(--muted)]">
          Model-native score {entity.model_native_confidence.value} from {entity.model_native_confidence.origin}.{" "}
          {entity.model_native_confidence.calibration_status.replaceAll("_", " ")}.
        </p>
      )}
      <ul className="mt-3 space-y-2">
        {records.map((record) => (
          <li key={record.id} className="rounded-2xl bg-black/25 p-2 text-xs">
            <ClassMark record={record} />
            <p className="mt-1 text-[var(--muted)]">{record.notes}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-black/20 p-2">
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="mt-1 break-words">{value.replaceAll("_", " ")}</dd>
    </div>
  );
}

function ClassMark({ record }: { record: Provenance }) {
  const tone =
    record.provenance_class === "observed"
      ? "text-[var(--ink)]"
      : record.provenance_class === "vision_estimated"
        ? "text-[var(--blue)]"
        : record.provenance_class === "generative"
          ? "text-[var(--violet)]"
          : "text-[var(--amber)]";
  return <p className={`uppercase tracking-wider ${tone}`}>{record.provenance_class.replaceAll("_", " ")}</p>;
}

function Audit({ memory, selected, onSelect }: { memory: Memory; selected: Entity | null; onSelect: (entity: Entity) => void }) {
  const counts = memory.provenances.reduce<Record<string, number>>((map, record) => {
    map[record.provenance_class] = (map[record.provenance_class] || 0) + 1;
    return map;
  }, {});
  return (
    <div className="grid gap-3 lg:grid-cols-[280px_1fr]">
      <div className="glass max-h-[75vh] overflow-auto rounded-3xl p-3">
        {memory.entities.map((entity) => (
          <button
            key={entity.id}
            onClick={() => onSelect(entity)}
            className={`mb-1 w-full rounded-2xl px-3 py-2 text-left text-sm ${selected?.id === entity.id ? "bg-white/10" : "hover:bg-white/5"}`}
          >
            <span className="capitalize">{entity.label}</span>
            <span className="mt-1 block text-xs text-[var(--muted)]">{entity.content_status.replaceAll("_", " ")}</span>
          </button>
        ))}
      </div>
      <div className="space-y-3">
        <div className="glass rounded-3xl p-5">
          <p className="kicker">What the record contains</p>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted)]">{memory.scene_description.text}</p>
          <p className="mt-2 text-xs text-[var(--gold)]">Description origin: {memory.scene_description.origin}</p>
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            {Object.entries(counts).map(([key, value]) => (
              <span key={key} className="rounded-full border border-[var(--line)] px-3 py-1">
                {key.replaceAll("_", " ")} · {value}
              </span>
            ))}
          </div>
        </div>
        <div className="glass rounded-3xl p-5">
          <p className="kicker">Model trace</p>
          <ul className="mt-3 space-y-2">
            {memory.invocations.map((item) => (
              <li key={item.id} className="grid gap-1 border-b border-[var(--line)] py-2 text-sm md:grid-cols-[180px_1fr_auto]">
                <span>{item.model_id}</span>
                <span className="text-[var(--muted)]">{item.output_summary}</span>
                <span className={item.live && item.status === "succeeded" ? "text-[var(--gold)]" : "text-[var(--muted)]"}>
                  {item.status}
                  {item.live ? " · live Meta" : ""}
                  {item.duration_ms != null ? ` · ${Math.round(item.duration_ms)} ms` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
        {selected && <ProvenanceCard memory={memory} entity={selected} />}
      </div>
    </div>
  );
}

function Graph({ memory }: { memory: Memory }) {
  const nodes = [
    { id: memory.id, label: memory.title, kind: "memory" },
    ...memory.entities
      .filter((entity) => !["wall", "floor", "region"].includes(entity.label))
      .map((entity) => ({ id: entity.id, label: entity.label, kind: "entity" })),
    ...memory.testimonies.map((item) => ({ id: item.id, label: item.speaker || "testimony", kind: "testimony" })),
    ...memory.hypotheses.map((item) => ({ id: item.id, label: item.title, kind: "hypothesis" })),
  ];
  return (
    <div className="glass rounded-3xl p-5">
      <p className="kicker">ChronosGraph</p>
      <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
        Links between photographs are proposals until you confirm them. A shared label and a color correlation are not identity.
      </p>
      <div className="mt-6 grid gap-4 md:grid-cols-[1fr_280px]">
        <svg viewBox="0 0 640 420" className="h-auto w-full">
          {nodes.map((node, index) => {
            const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
            const radius = node.kind === "memory" ? 0 : 150;
            const x = 320 + Math.cos(angle) * radius;
            const y = 210 + Math.sin(angle) * radius * 0.72;
            const color =
              node.kind === "memory"
                ? "#f3eee6"
                : node.kind === "testimony"
                  ? "#e2a45c"
                  : node.kind === "hypothesis"
                    ? "#c3b0e4"
                    : "#8eb6ff";
            return (
              <g key={node.id}>
                {node.kind !== "memory" && <line x1="320" y1="210" x2={x} y2={y} stroke="rgba(243,238,230,0.25)" />}
                <circle cx={x} cy={y} r={node.kind === "memory" ? 18 : 8} fill={color} />
                <text x={x + 12} y={y + 4} fill="#f3eee6" fontSize="12">
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="space-y-3 text-sm">
          {memory.links.length === 0 && <p className="text-[var(--muted)]">No cross-photograph proposals yet.</p>}
          {memory.links.map((link) => (
            <article key={link.id} className="rounded-2xl bg-black/25 p-3">
              <p className="capitalize">
                {link.a.label} · {link.status}
              </p>
              <p className="mt-1 text-xs text-[var(--muted)]">{link.note}</p>
              <p className="mt-1 text-xs">{link.cues.join(" · ")}</p>
              {link.status === "proposed" && (
                <div className="mt-2 flex gap-2">
                  <Button variant="gold" onClick={() => setLink(link.id, "confirmed")}>
                    Confirm
                  </Button>
                  <Button variant="ghost" onClick={() => setLink(link.id, "rejected")}>
                    Reject
                  </Button>
                </div>
              )}
            </article>
          ))}
          <Timeline memory={memory} />
        </div>
      </div>
    </div>
  );
}

function Timeline({ memory }: { memory: Memory }) {
  const events = memory.collection_timeline || [];
  return (
    <div>
      <p className="kicker">Capture timeline</p>
      {events.length < 2 ? (
        <p className="mt-2 text-xs text-[var(--muted)]">
          A historical sequence appears only when at least two photographs carry an EXIF time you authorized, or a date a person asserted.
          This record does not invent one.
        </p>
      ) : (
        <ol className="mt-2 space-y-2 text-xs">
          {events.map((event) => (
            <li key={event.memory_id}>
              {event.at} · {event.title} · {event.reliability.replaceAll("_", " ")}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

async function setLink(id: string, status: string) {
  await fetch(`/api/links/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  window.location.reload();
}

function Realities({
  memory,
  onCreate,
  onChoose,
  busy,
}: {
  memory: Memory;
  onCreate: (claim: string) => Promise<void>;
  onChoose: (id: string | null) => Promise<void>;
  busy: boolean;
}) {
  const [claim, setClaim] = useState("A piano stood in the dark corner.");
  return (
    <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="glass overflow-hidden rounded-3xl">
        <img src={fileUrl(memory.photograph.url)} alt="" className="max-h-[70vh] w-full object-contain" />
      </div>
      <div className="glass rounded-3xl p-5">
        <p className="kicker">Alternative memory realities</p>
        <p className="mt-2 text-sm text-[var(--muted)]">
          A branch is a hypothesis. It never overwrites the photograph. If a generator runs, only the unobserved mask is allowed to change.
        </p>
        <button
          className={`mt-4 w-full rounded-2xl px-3 py-3 text-left ${memory.active_hypothesis_id ? "bg-black/20" : "bg-white/10"}`}
          onClick={() => onChoose(null)}
        >
          Original evidence
          <span className="mt-1 block text-xs text-[var(--muted)]">Photographed pixels only.</span>
        </button>
        {memory.hypotheses.map((item) => (
          <button
            key={item.id}
            className={`mt-2 w-full rounded-2xl px-3 py-3 text-left ${memory.active_hypothesis_id === item.id ? "bg-white/10" : "bg-black/20"}`}
            onClick={() => onChoose(item.id)}
          >
            {item.title}
            <span className="mt-1 block text-xs text-[var(--muted)]">
              {item.generator.model_id}
              {item.generator.live ? " · live" : " · sketch"} · {item.status}
            </span>
          </button>
        ))}
        <textarea
          value={claim}
          onChange={(event) => setClaim(event.target.value)}
          className="mt-4 h-24 w-full rounded-2xl border border-[var(--line)] bg-black/30 p-3 text-sm outline-none"
        />
        <Button className="mt-3" variant="gold" disabled={busy} onClick={() => onCreate(claim)}>
          Create hypothesis
        </Button>
      </div>
    </div>
  );
}
