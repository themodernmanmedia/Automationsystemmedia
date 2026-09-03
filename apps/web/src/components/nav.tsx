'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const SECTIONS = [
  { group: 'Operate', items: [
    { href: '/', label: 'Overview' },
    { href: '/automation', label: 'Automation' },
    { href: '/content', label: 'Content' },
  ]},
  { group: 'Measure', items: [
    { href: '/analytics', label: 'Analytics' },
  ]},
  { group: 'Configure', items: [
    { href: '/accounts', label: 'Social Accounts' },
    { href: '/capabilities', label: 'Platform Limits' },
  ]},
];

export function Nav() {
  const pathname = usePathname();
  if (pathname === '/login') return null;

  return (
    <nav className="flex w-60 shrink-0 flex-col border-r border-ink-border bg-ink-soft">
      <div className="border-b border-ink-border px-5 py-6">
        <div className="font-display text-lg leading-tight tracking-tightest text-bone">
          The Modern Man
        </div>
        <div className="mt-1 text-[10px] font-medium uppercase tracking-[0.2em] text-gold">
          Operating System
        </div>
      </div>

      <div className="flex-1 space-y-6 px-3 py-5">
        {SECTIONS.map((section) => (
          <div key={section.group}>
            <div className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-bone-dim">
              {section.group}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`block rounded-md px-3 py-2 text-sm transition-colors ${
                      active
                        ? 'bg-ink-raised font-medium text-bone'
                        : 'text-bone-muted hover:bg-ink-raised/50 hover:text-bone'
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-ink-border px-5 py-4 text-[11px] text-bone-dim">
        v0.1.0
      </div>
    </nav>
  );
}
