/**
 * Shared presentation primitives.
 *
 * `Unavailable` and `MetricValue` exist to serve the project's central rule:
 * the interface must never imply data or capability it does not have. A metric
 * a platform refuses to report renders as "not reported", never as 0.
 */
import type { ReactNode } from 'react';

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="flex items-start justify-between gap-6 border-b border-ink-border px-8 py-6">
      <div>
        <h1 className="font-display text-2xl tracking-tightest text-bone">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-bone-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Stat({ label, value, hint, tone = 'default' }: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: 'default' | 'ok' | 'warn' | 'error';
}) {
  const toneClass = {
    default: 'text-bone',
    ok: 'text-state-ok',
    warn: 'text-state-warn',
    error: 'text-state-error',
  }[tone];

  return (
    <div className="card card-pad">
      <div className="label">{label}</div>
      <div className={`stat mt-2 ${toneClass}`}>{value}</div>
      {hint && <div className="mt-1.5 text-xs text-bone-dim">{hint}</div>}
    </div>
  );
}

const STATUS_STYLES: Record<string, string> = {
  ok: 'border-state-ok/40 bg-state-ok/10 text-state-ok',
  warn: 'border-state-warn/40 bg-state-warn/10 text-state-warn',
  error: 'border-state-error/40 bg-state-error/10 text-state-error',
  idle: 'border-ink-border bg-ink-raised text-bone-dim',
};

export function StatusPill({ tone, children }: { tone: 'ok' | 'warn' | 'error' | 'idle'; children: ReactNode }) {
  return (
    <span className={`pill ${STATUS_STYLES[tone]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}

/**
 * Renders a capability the platform's API genuinely does not offer. The reason
 * is always shown, so the operator learns why rather than assuming a bug.
 */
export function Unavailable({ reason }: { reason?: string }) {
  return (
    <div className="rounded-md border border-dashed border-ink-border bg-ink/40 px-3 py-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-bone-dim">
        Not supported by current API
      </div>
      {reason && <div className="mt-1 text-xs leading-relaxed text-bone-dim">{reason}</div>}
    </div>
  );
}

/**
 * A metric that may legitimately be absent. Null means the platform will not
 * report it — printing 0 would be a fabrication, and would also corrupt any
 * judgment made from this screen.
 */
export function MetricValue({ value, format = 'number' }: { value: number | null | undefined; format?: 'number' | 'percent' }) {
  if (value === null || value === undefined) {
    return <span className="text-sm italic text-bone-dim">not reported</span>;
  }
  if (format === 'percent') return <>{(value * 100).toFixed(1)}%</>;
  return <>{value.toLocaleString()}</>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center justify-center px-8 py-16 text-center">
      <div className="font-display text-lg text-bone">{title}</div>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-bone-muted">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorPanel({ title, message }: { title: string; message: string }) {
  return (
    <div className="card card-pad border-state-error/40">
      <div className="font-medium text-state-error">{title}</div>
      <p className="mt-1.5 text-sm leading-relaxed text-bone-muted">{message}</p>
    </div>
  );
}
