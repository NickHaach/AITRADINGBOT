"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  fetchAutopilot,
  fetchBlotter,
  fetchJournal,
  startAutopilot,
  stopAutopilot,
  updateAutopilot,
  type AutopilotStatus,
  type BlotterEvent,
  type JournalEntry,
  type JournalResponse,
} from "@/lib/api";

function pct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function money(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function timeLabel(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16);
  }
}

function eventTitle(e: BlotterEvent): string {
  if (e.type === "fill") return `${(e.side || "trade").toUpperCase()} ${e.ticker}`;
  if (e.type === "reject") return `REJECT ${e.ticker}`;
  if (e.type === "close") return `CLOSE ${e.ticker}`;
  if (e.type === "cycle") return "CYCLE";
  return e.type.toUpperCase();
}

function eventDetail(e: BlotterEvent): string {
  if (e.type === "fill") {
    return `${e.qty ?? "?"} @ ${e.price ?? "—"}`;
  }
  if (e.type === "reject") {
    return (e.reasons || []).join(", ") || "risk / broker";
  }
  if (e.type === "close") {
    const pnl = e.pnl != null ? money(Number(e.pnl)) : "—";
    const hit = e.correct_direction ? "hit" : "miss";
    return `PnL ${pnl} · ${hit}`;
  }
  if (e.type === "cycle") {
    const src = (e.sources || []).slice(0, 3).join(" · ");
    return `${e.approved_trades ?? 0} filled · ${e.rejected_trades ?? 0} blocked${src ? ` · ${src}` : ""}`;
  }
  return "";
}

export function ActivityPanel({
  canTrade,
  refreshKey,
}: {
  canTrade: boolean;
  refreshKey: number;
}) {
  const [tab, setTab] = useState<"blotter" | "journal" | "autopilot">("blotter");
  const [events, setEvents] = useState<BlotterEvent[]>([]);
  const [journal, setJournal] = useState<JournalResponse | null>(null);
  const [auto, setAuto] = useState<AutopilotStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [intervalMin, setIntervalMin] = useState(15);
  const [quietStart, setQuietStart] = useState(22);
  const [quietEnd, setQuietEnd] = useState(6);
  const [kill, setKill] = useState(false);

  async function load() {
    const [b, j, a] = await Promise.all([fetchBlotter(80), fetchJournal(50), fetchAutopilot()]);
    setEvents(b.events);
    setJournal(j);
    if (a) {
      setAuto(a);
      setIntervalMin(a.interval_minutes);
      setQuietStart(a.quiet_start_hour);
      setQuietEnd(a.quiet_end_hour);
      setKill(a.kill_switch);
    }
  }

  useEffect(() => {
    void load();
  }, [refreshKey]);

  useEffect(() => {
    if (tab !== "autopilot") return;
    const id = setInterval(() => {
      void fetchAutopilot().then((a) => a && setAuto(a));
    }, 8000);
    return () => clearInterval(id);
  }, [tab]);

  async function onSaveAutopilot(e: FormEvent) {
    e.preventDefault();
    if (!canTrade) return;
    setBusy(true);
    setError(null);
    try {
      const next = await updateAutopilot({
        enabled: auto?.enabled ?? false,
        interval_minutes: intervalMin,
        quiet_start_hour: quietStart,
        quiet_end_hour: quietEnd,
        kill_switch: kill,
        tickers: auto?.tickers ?? null,
      });
      setAuto(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function onToggleAutopilot() {
    if (!canTrade) return;
    setBusy(true);
    setError(null);
    try {
      const next = auto?.enabled ? await stopAutopilot() : await startAutopilot();
      setAuto(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Toggle failed");
    } finally {
      setBusy(false);
    }
  }

  const stats = journal?.stats;

  return (
    <div className="fade-up space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="section-title text-[1.5rem] md:text-[1.65rem]">Activity</h2>
          <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-mist/40">
            Blotter · journal · autopilot
          </p>
        </div>
        <div className="flex border border-line">
          {(
            [
              ["blotter", "Blotter"],
              ["journal", "Journal"],
              ["autopilot", "Autopilot"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-3.5 py-2 font-mono text-[10px] uppercase tracking-[0.14em] ${
                tab === id ? "bg-signal text-ink" : "text-mist/50 hover:text-ivory"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="font-mono text-[11px] text-danger">{error}</p> : null}

      {tab === "blotter" ? (
        <div className="border border-line">
          {events.length === 0 ? (
            <p className="px-5 py-12 text-center text-sm text-mist/45">
              No activity yet — run a cycle to populate the blotter.
            </p>
          ) : (
            <ul className="divide-y divide-line max-h-[32rem] overflow-y-auto">
              {events.map((ev, i) => (
                <li
                  key={`${ev.type}-${ev.at}-${ev.ticker}-${i}`}
                  className="grid grid-cols-[5.5rem_1fr_auto] items-baseline gap-3 px-4 py-3 md:grid-cols-[6.5rem_7rem_1fr_auto]"
                >
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-mist/35">
                    {timeLabel(ev.at)}
                  </span>
                  <span
                    className={`font-mono text-[10px] uppercase tracking-[0.14em] ${
                      ev.type === "fill"
                        ? "text-gain"
                        : ev.type === "reject"
                          ? "text-danger"
                          : ev.type === "close"
                            ? "text-signal"
                            : "text-mist/55"
                    }`}
                  >
                    {eventTitle(ev)}
                  </span>
                  <span className="col-span-2 font-mono text-[11px] text-mist/55 md:col-span-1">
                    {eventDetail(ev)}
                  </span>
                  <span className="hidden font-mono text-[9px] text-mist/25 md:inline">
                    {(ev.cycle_id || "").slice(0, 8)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {tab === "journal" ? (
        <div className="space-y-5">
          <div className="grid gap-0 border border-line sm:grid-cols-4">
            <Stat
              label="Samples"
              value={stats ? String(stats.sampleSize) : "—"}
            />
            <Stat label="Direction hit" value={pct(stats?.directionAccuracy)} />
            <Stat
              label="Avg actual"
              value={pct(stats?.avgActualReturn)}
              tone={(stats?.avgActualReturn ?? 0) >= 0 ? "gain" : "danger"}
            />
            <Stat
              label="Temp"
              value={journal ? journal.calibration.temperature.toFixed(2) : "—"}
              hint={`${journal?.openLots ?? 0} open lots`}
            />
          </div>

          {!journal?.entries.length ? (
            <p className="border border-dashed border-line px-5 py-12 text-center text-sm text-mist/45">
              Closed trades appear here after horizons mature (paper days advance each cycle).
            </p>
          ) : (
            <ul className="divide-y divide-line border border-line">
              {journal.entries.map((entry: JournalEntry) => (
                <li key={entry.id} className="px-4 py-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div className="flex items-baseline gap-3">
                      <h3 className="font-display text-xl tracking-tight text-ivory">{entry.ticker}</h3>
                      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/45">
                        {entry.action}
                      </span>
                      <span
                        className={`font-mono text-[10px] uppercase tracking-[0.14em] ${
                          entry.correctDirection ? "text-gain" : "text-danger"
                        }`}
                      >
                        {entry.correctDirection ? "Hit" : "Miss"}
                      </span>
                    </div>
                    <span
                      className={`font-mono text-[12px] tabular-nums ${
                        entry.pnl >= 0 ? "text-gain" : "text-danger"
                      }`}
                    >
                      {entry.pnl >= 0 ? "+" : ""}
                      {money(entry.pnl)}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 font-mono text-[10px] text-mist/40">
                    <span>pred {pct(entry.predictedReturn)}</span>
                    <span>act {pct(entry.actualReturn)}</span>
                    <span>conf {pct(entry.confidence)}</span>
                    <span>{entry.holdingDays}d</span>
                    <span>{timeLabel(entry.closedAt)}</span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-[13px] leading-snug text-mist/55">
                    {entry.thesis || entry.newsExcerpt || "—"}
                  </p>
                  {entry.sources?.length ? (
                    <p className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.12em] text-mist/30">
                      {entry.sources.join(" · ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {tab === "autopilot" ? (
        <div className="border border-line bg-[rgba(10,16,22,0.55)] px-5 py-6 md:px-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    auto?.enabled
                      ? auto.kill_switch || auto.in_quiet_hours
                        ? "bg-warn"
                        : "bg-gain pulse-dot"
                      : "bg-mist/35"
                  }`}
                />
                <p className="font-display text-2xl tracking-tight text-ivory">
                  {auto?.enabled ? "Autopilot on" : "Autopilot off"}
                </p>
              </div>
              <p className="mt-2 max-w-lg text-sm leading-relaxed text-mist/60">
                Schedules intel-backed cycles on an interval. Quiet hours (UTC) pause runs; kill
                switch blocks all trading until disarmed.
              </p>
              <p className="mt-3 font-mono text-[10px] text-mist/40">
                {auto?.runs ?? 0} auto runs · last {timeLabel(auto?.last_run_at)} · next{" "}
                {auto?.enabled ? timeLabel(auto?.next_run_at) : "—"}
                {auto?.in_quiet_hours ? " · quiet now" : ""}
                {auto?.kill_switch ? " · kill armed" : ""}
              </p>
              {auto?.last_error ? (
                <p className="mt-2 font-mono text-[11px] text-warn">{auto.last_error}</p>
              ) : null}
            </div>
            {canTrade ? (
              <button
                type="button"
                className={`desk-btn ${auto?.enabled ? "desk-btn-ghost" : "desk-btn-primary"}`}
                disabled={busy}
                onClick={onToggleAutopilot}
              >
                {auto?.enabled ? "Stop" : "Start"}
              </button>
            ) : (
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist/35">
                Trader role required
              </p>
            )}
          </div>

          <form
            onSubmit={onSaveAutopilot}
            className="mt-8 grid gap-4 border-t border-line pt-6 md:grid-cols-4 md:items-end"
          >
            <label className="block font-mono text-[10px] uppercase tracking-[0.14em] text-mist/40">
              Interval (min)
              <input
                type="number"
                min={1}
                max={240}
                className="desk-input mt-2"
                value={intervalMin}
                onChange={(e) => setIntervalMin(Number(e.target.value) || 15)}
                disabled={!canTrade}
              />
            </label>
            <label className="block font-mono text-[10px] uppercase tracking-[0.14em] text-mist/40">
              Quiet start (UTC)
              <input
                type="number"
                min={0}
                max={23}
                className="desk-input mt-2"
                value={quietStart}
                onChange={(e) => setQuietStart(Number(e.target.value))}
                disabled={!canTrade}
              />
            </label>
            <label className="block font-mono text-[10px] uppercase tracking-[0.14em] text-mist/40">
              Quiet end (UTC)
              <input
                type="number"
                min={0}
                max={23}
                className="desk-input mt-2"
                value={quietEnd}
                onChange={(e) => setQuietEnd(Number(e.target.value))}
                disabled={!canTrade}
              />
            </label>
            <div className="flex flex-col gap-3">
              <label className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-mist/50">
                <input
                  type="checkbox"
                  checked={kill}
                  onChange={(e) => setKill(e.target.checked)}
                  disabled={!canTrade}
                  className="accent-[var(--signal)]"
                />
                Kill switch
              </label>
              {canTrade ? (
                <button type="submit" className="desk-btn desk-btn-ghost" disabled={busy}>
                  {busy ? "…" : "Save settings"}
                </button>
              ) : null}
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "gain" | "danger";
}) {
  return (
    <div className="border-b border-line px-4 py-4 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
      <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-mist/35">{label}</p>
      <p
        className={`mt-1.5 font-display text-2xl tabular-nums tracking-tight ${
          tone === "gain" ? "text-gain" : tone === "danger" ? "text-danger" : "text-ivory"
        }`}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 font-mono text-[9px] text-mist/30">{hint}</p> : null}
    </div>
  );
}
