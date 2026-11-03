"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState } from "react";
import { fileUrl } from "@/lib/utils";

type Card = {
  id: string;
  title: string;
  sample: boolean;
  sample_note: string | null;
  photo_url: string;
  labels: string[];
  live_meta: boolean;
  capture_time: string | null;
  capture_time_reliability: string;
};

export default function HomePage() {
  const [memories, setMemories] = useState<Card[] | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    fetch("/api/memories")
      .then((response) => response.json())
      .then((body) => {
        setMemories(body.memories || []);
        setOffline(Boolean(body.error));
      })
      .catch(() => {
        setMemories([]);
        setOffline(true);
      });
  }, []);

  return (
    <main className="px-4 pb-16 md:px-8">
      <section className="grid items-end gap-8 py-8 md:grid-cols-[1.2fr_0.8fr] md:py-14">
        <div>
          <p className="kicker">A photograph is a window into a world</p>
          <h1 className="serif mt-3 max-w-3xl text-4xl leading-tight md:text-6xl">
            Step inside the picture. Keep sight of what is real, estimated, and imagined.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-[var(--muted)]">
            ChronoSpace turns one photograph into a depth-aware space you can look around, then keeps the original pixels,
            the vision estimates, any generated fill, and anyone’s recollection in separate records.
          </p>
          <div className="mt-6 flex gap-3">
            <Link href="/import" className="rounded-full bg-[var(--gold)] px-5 py-2 text-sm text-[#24180f]">
              Import a photograph
            </Link>
            {memories?.[0] && (
              <Link href={`/memory/${memories[0].id}`} className="rounded-full border border-[var(--line)] px-5 py-2 text-sm">
                Open a memory
              </Link>
            )}
          </div>
        </div>
        <div className="glass overflow-hidden rounded-[28px]">
          {memories?.[0] ? (
            <Image
              src={fileUrl(memories[0].photo_url)}
              alt=""
              width={960}
              height={640}
              unoptimized
              className="aspect-[3/2] w-full object-cover"
            />
          ) : (
            <div className="aspect-[3/2] bg-[#1a1815]" />
          )}
        </div>
      </section>
      {offline && (
        <p className="mb-4 text-sm text-[var(--danger)]">
          The vision service is not answering. Start it with the documented command, then refresh.
        </p>
      )}
      <section>
        <h2 className="serif text-2xl">Memories</h2>
        {memories && memories.length === 0 && !offline && (
          <p className="mt-3 max-w-lg text-sm text-[var(--muted)]">
            Nothing has been reconstructed yet. Import a photograph, or restart the vision service to seed the painted reference interior.
          </p>
        )}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {memories?.map((memory) => (
            <Link key={memory.id} href={`/memory/${memory.id}`} className="glass overflow-hidden rounded-3xl">
              <Image
                src={fileUrl(memory.photo_url)}
                alt=""
                width={960}
                height={640}
                unoptimized
                className="aspect-[3/2] w-full object-cover"
              />
              <div className="p-4">
                <h3 className="serif text-xl">{memory.title}</h3>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  {memory.sample ? "Painted reference" : "Upload"} · {memory.labels.slice(0, 4).join(", ") || "regions"}
                </p>
                <p className="mt-2 text-xs text-[var(--gold)]">
                  {memory.live_meta ? "Includes a live Meta response" : "Local models only"}
                  {memory.capture_time ? ` · ${memory.capture_time_reliability.replaceAll("_", " ")}` : ""}
                </p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
