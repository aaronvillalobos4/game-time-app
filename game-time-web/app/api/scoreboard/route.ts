import { LEAGUES, type League, normalizeScoreboard } from "../../../lib/scoreboard";

export async function GET(request: Request) {
  const league = new URL(request.url).searchParams.get("league") ?? "nfl";
  if (!Object.hasOwn(LEAGUES, league)) return Response.json({ error: "Unsupported league" }, { status: 400 });
  try {
    const response = await fetch(`https://site.api.espn.com/apis/site/v2/sports/${LEAGUES[league as League].path}/scoreboard?limit=100`, {
      next: { revalidate: 60 }, signal: AbortSignal.timeout(8_000),
    });
    if (!response.ok) throw new Error("Scoreboard unavailable");
    return Response.json({ games: normalizeScoreboard(await response.json()) }, { headers: { "Cache-Control": "public, max-age=60" } });
  } catch {
    return Response.json({ error: "Scores are temporarily unavailable." }, { status: 502 });
  }
}
