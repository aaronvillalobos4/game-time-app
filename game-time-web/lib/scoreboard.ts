export const LEAGUES = {
  nfl: { label: "NFL", path: "football/nfl" },
  college: { label: "College football", path: "football/college-football" },
  nba: { label: "NBA", path: "basketball/nba" },
  mlb: { label: "MLB", path: "baseball/mlb" },
  nhl: { label: "NHL", path: "hockey/nhl" },
} as const;
export type League = keyof typeof LEAGUES;
export type ScoreGame = { id: string; name: string; date: string; status: string; live: boolean; teams: { name: string; score: string }[]; url: string };
type EspnEvent = {
  id?: string; name?: string; date?: string; links?: { href?: string }[];
  status?: { type?: { state?: string; shortDetail?: string } };
  competitions?: { competitors?: { homeAway?: string; score?: string; team?: { abbreviation?: string; displayName?: string } }[] }[];
};

export function normalizeScoreboard(data: { events?: EspnEvent[] }): ScoreGame[] {
  if (!Array.isArray(data.events)) throw new Error("Invalid scoreboard response");
  return data.events.filter((event) => event?.id && event.competitions?.[0]?.competitors?.length === 2).map((event) => {
    const state = event.status?.type?.state;
    const teams = [...(event.competitions?.[0]?.competitors ?? [])].sort((a, b) => Number(a.homeAway === "home") - Number(b.homeAway === "home"));
    const url = event.links?.map((link) => link.href).find((href) => {
      try { const link = new URL(href ?? ""); return link.protocol === "https:" && (link.hostname === "espn.com" || link.hostname.endsWith(".espn.com")); } catch { return false; }
    }) ?? "https://www.espn.com/scoreboard/";
    return {
      id: event.id!, name: event.name ?? "Game details", date: event.date ?? "",
      status: event.status?.type?.shortDetail ?? "Time TBD", live: state === "in", url,
      teams: teams.map((team) => ({ name: team.team?.abbreviation ?? team.team?.displayName ?? "TBD", score: state === "in" || state === "post" ? String(team.score ?? "–") : "–" })),
    };
  }).sort((a, b) => Number(b.live) - Number(a.live)).slice(0, 30);
}
