import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 flex items-center justify-between px-4 py-3 md:px-8">
      <Link href="/" className="flex items-baseline gap-3">
        <span className="serif text-xl tracking-tight">ChronoSpace</span>
        <span className="kicker hidden sm:inline">Epistemic memory</span>
      </Link>
      <nav className="flex items-center gap-4 text-sm text-[var(--muted)]">
        <Link href="/import" className="hover:text-[var(--ink)]">
          Import
        </Link>
        <Link href="/" className="hover:text-[var(--ink)]">
          Memories
        </Link>
      </nav>
    </header>
  );
}
