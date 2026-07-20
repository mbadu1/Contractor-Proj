"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Market Overview" },
  { href: "/businesses", label: "Business Explorer" },
  { href: "/comparisons", label: "Comparisons" },
  { href: "/model-health", label: "Model Health" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-ink-600/80 bg-ink-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-6 px-5 py-3">
        <Link href="/" className="group flex items-baseline gap-2">
          <span className="font-mono text-lg font-semibold tracking-tight text-mist-100">
            RevWatch
          </span>
          <span className="hidden text-[10px] uppercase tracking-[0.2em] text-mist-400 sm:inline">
            revenue intelligence
          </span>
        </Link>
        <nav className="flex flex-wrap items-center gap-1">
          {NAV.map((item) => {
            const active = item.href === "/" ? path === "/" : path.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded px-3 py-1.5 text-sm transition ${
                  active
                    ? "bg-ink-700 text-accent-glow"
                    : "text-mist-300 hover:bg-ink-800 hover:text-mist-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
