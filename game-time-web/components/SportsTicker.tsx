"use client";

import { useEffect, useRef, useState } from "react";
import { LEAGUES, type League, type ScoreGame } from "../lib/scoreboard";

export default function SportsTicker() {
  const [league, setLeague] = useState<League>("nfl");
  const [games, setGames] = useState<ScoreGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updated, setUpdated] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(true);
  const lastLeague = useRef<League | null>(null);

  useEffect(() => {
    let disposed = false;
    let pending = false;
    const controller = new AbortController();
    const refresh = async () => {
      if (pending) return;
      pending = true;
      try {
        const response = await fetch(`/api/scoreboard?league=${league}`, { signal: controller.signal });
        if (!response.ok) throw new Error("Unavailable");
        const data = await response.json() as { games: ScoreGame[] };
        if (!disposed) {
          setGames(data.games); setError(null);
          setUpdated(new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }));
        }
      } catch {
        if (!disposed) setError("Scores unavailable — any displayed scores may be out of date.");
      } finally {
        pending = false;
        if (!disposed) setLoading(false);
      }
    };
    if (refreshing || lastLeague.current !== league) void refresh();
    lastLeague.current = league;
    const timer = refreshing ? window.setInterval(() => { if (!document.hidden) void refresh(); }, 60_000) : undefined;
    return () => { disposed = true; controller.abort(); if (timer) window.clearInterval(timer); };
  }, [league, refreshing]);

  const chooseLeague = (choice: League) => {
    if (choice === league) return;
    setLeague(choice); setGames([]); setLoading(true); setError(null); setUpdated(null);
  };

  return (
    <section aria-label="ESPN sports scoreboard" className="rounded-2xl border border-slate-700 bg-slate-950 p-3 print:hidden">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded bg-red-600 px-2 py-1 font-bold uppercase tracking-wide">Scoreboard</span>
          <a href="https://www.espn.com/scoreboard/" target="_blank" rel="noopener noreferrer" className="text-slate-300 underline underline-offset-2">Scores from ESPN ↗</a>
        </div>
        <button type="button" onClick={() => setRefreshing((value) => !value)} aria-pressed={refreshing} className="text-xs text-slate-400 hover:text-white">{refreshing ? "Pause updates" : "Resume updates"}</button>
      </div>
      <div className="mb-3 flex flex-wrap gap-1" aria-label="Choose a league">
        {(Object.keys(LEAGUES) as League[]).map((choice) => <button type="button" key={choice} aria-pressed={league === choice} onClick={() => chooseLeague(choice)} className={`rounded-full px-3 py-1 text-xs font-semibold ${league === choice ? "bg-white text-slate-950" : "bg-slate-800 text-slate-300 hover:bg-slate-700"}`}>{LEAGUES[choice].label}</button>)}
      </div>
      <p role="status" className="mb-2 text-xs text-slate-400">{loading ? "Loading scores…" : error ?? (games.length ? `Checked ${updated}. ${refreshing ? "Refreshes every minute." : "Updates paused."}` : "No games currently listed for this league.")}</p>
      <div key={league} tabIndex={0} role="region" aria-label="Game scores — scroll horizontally for more" className="flex gap-2 overflow-x-auto pb-2 focus-visible:outline-2 focus-visible:outline-red-400">
        {games.map((game) => (
          <a key={game.id} href={game.url} target="_blank" rel="noopener noreferrer" aria-label={`${game.name}: ${game.status}. View on ESPN`} className="w-44 shrink-0 rounded-xl border border-slate-700 bg-slate-900 p-3 hover:border-red-400 focus-visible:outline-2 focus-visible:outline-red-400">
            <p className={`mb-2 text-xs font-semibold ${game.live ? "text-emerald-400" : "text-slate-400"}`}>{game.live ? "● LIVE · " : ""}{game.status}</p>
            {game.teams.map((team, index) => <div key={index} className="flex justify-between gap-3 text-sm font-bold"><span>{team.name}</span><span className="tabular-nums">{team.score}</span></div>)}
            {game.date && !Number.isNaN(Date.parse(game.date)) && <p className="mt-2 text-[11px] text-slate-400">{new Date(game.date).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })} (local)</p>}
          </a>
        ))}
      </div>
      {games.length > 3 && <p className="text-right text-xs text-slate-400">Scroll for more games →</p>}
    </section>
  );
}
