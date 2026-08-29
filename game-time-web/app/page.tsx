"use client";

import Image from "next/image";
import Script from "next/script";
import { FormEvent, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://game-time-f7qt.onrender.com";
const INITIAL_MESSAGE = "Welcome to Game Time! What game or sports matchup do you want to go see?";
const LOADING_STEPS = [
  "🎟️ Scouting ticket options and stadium seating...",
  "✈️ Comparing flight schedules and airline rates...",
  "🏨 Checking top-rated hotels near the arena...",
  "📊 Verifying prices against your budget...",
  "📝 Formatting your custom trip itinerary...",
];
const PROMPT_CHIPS = [
  "🏈 Cowboys vs Eagles in Dallas",
  "⚾ Astros vs Rangers in Houston",
  "🏀 Lakers in LA with $1500 budget",
  "🏒 Golden Knights in Vegas flying from Austin",
];

type Message = { sender: "user" | "bot"; text: string };
type TripSlots = {
  event?: string | null;
  date?: string | null;
  needs_flight?: boolean | null;
  departure_city?: string | null;
  budget?: number | null;
};
type ParseResponse = {
  is_reset?: boolean;
  is_complete: boolean;
  slots: TripSlots;
  follow_up_question?: string | null;
};
type StreamEvent = {
  type?: "status" | "token" | "error";
  content?: string;
  text?: string;
  result?: string;
};

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([{ sender: "bot", text: INITIAL_MESSAGE }]);
  const [input, setInput] = useState("");
  const [slots, setSlots] = useState<TripSlots>({});
  const [itinerary, setItinerary] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(
      () => setLoadingStep((step) => (step + 1) % LOADING_STEPS.length),
      6000,
    );
    return () => window.clearInterval(timer);
  }, [loading]);

  const addBotMessage = (text: string) => {
    setMessages((current) => [...current, { sender: "bot", text }]);
  };

  const generateItinerary = async (trip: TripSlots) => {
    if (!trip.event || !trip.date || trip.budget == null) {
      throw new Error("The trip was marked complete without all required details.");
    }

    addBotMessage(`Got it! Building your itinerary for ${trip.event} on ${trip.date}...`);
    const response = await fetch(`${API_URL}/api/itinerary-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event: trip.event,
        date: trip.date,
        departure_city: trip.departure_city || "Local",
        budget: trip.budget,
      }),
    });
    if (!response.ok) {
      throw new Error(`Itinerary request failed (${response.status}): ${await response.text()}`);
    }
    if (!response.body) throw new Error("The itinerary stream was empty.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let completeText = "";
    setItinerary("");

    const processEvent = (block: string) => {
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n")
        .trim();
      if (!data || data === "[DONE]") return;

      let event: StreamEvent;
      try {
        event = JSON.parse(data) as StreamEvent;
      } catch {
        event = { type: "token", content: data };
      }
      if (event.type === "error") throw new Error(event.content || "The agents returned an error.");
      if (event.type === "status") {
        setStatus(event.content || "");
        return;
      }
      const content = event.content ?? event.text ?? event.result ?? "";
      if (content) {
        completeText += content;
        setItinerary(completeText.trim());
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      blocks.forEach(processEvent);
      if (done) break;
    }
    if (buffer.trim()) processEvent(buffer);
    if (!completeText.trim()) throw new Error("The agents finished without returning an itinerary.");
  };

  const handleSend = async (rawText: string) => {
    const text = rawText.trim();
    if (!text || loading) return;

    setMessages((current) => [...current, { sender: "user", text }]);
    setInput("");
    setLoading(true);
    setLoadingStep(0);
    setStatus("");
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/parse-intent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, current_slots: slots }),
      });
      if (!response.ok) throw new Error(`Conversation request failed (${response.status}).`);

      const parsed = (await response.json()) as ParseResponse;
      if (parsed.is_reset) {
        setSlots({});
        setItinerary(null);
        setMessages([{ sender: "bot", text: parsed.follow_up_question || INITIAL_MESSAGE }]);
        return;
      }

      // Keep every field already collected. Only an explicit reset clears slots.
      const updatedSlots = parsed.slots ?? slots;
      setSlots(updatedSlots);
      if (!parsed.is_complete) {
        addBotMessage(parsed.follow_up_question || "What other trip detail can you provide?");
        return;
      }
      await generateItinerary(updatedSlots);
    } catch (caught: unknown) {
      console.error("Game Time error:", caught);
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
      setStatus("");
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handleSend(input);
  };

  const handleCopy = async () => {
    if (!itinerary) return;
    await navigator.clipboard.writeText(itinerary);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2500);
  };

  const handleEmail = () => {
    if (!itinerary) return;
    const subject = encodeURIComponent(`Game Time Itinerary: ${slots.event || "Sports Trip"}`);
    window.location.href = `mailto:?subject=${subject}&body=${encodeURIComponent(itinerary)}`;
  };

  const handleShare = async () => {
    if (!itinerary) return;
    if (!navigator.share) return handleCopy();
    try {
      await navigator.share({ title: `Game Time: ${slots.event || "Sports Trip"}`, text: itinerary });
    } catch (caught: unknown) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(getErrorMessage(caught));
    }
  };

  const markdownComponents = {
    a: (props: React.ComponentPropsWithoutRef<"a">) => (
      <a {...props} target="_blank" rel="noopener noreferrer" className="font-semibold text-red-400 underline hover:text-red-300" />
    ),
  };

  return (
    <main className="flex min-h-screen flex-col items-center bg-[#0f172a] p-6 text-white print:bg-white print:p-0 print:text-black">
      <Script strategy="afterInteractive" src="https://www.googletagmanager.com/gtag/js?id=G-CP8PCZ4F12" />
      <Script id="google-analytics" strategy="afterInteractive">
        {`window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-CP8PCZ4F12');`}
      </Script>

      <div className="my-4 w-full max-w-3xl space-y-6">
        <header className="flex flex-col items-center gap-2 text-center print:hidden">
          <Image src="/logo.png" alt="Game Time logo" width={100} height={100} priority className="h-auto max-h-20 w-auto object-contain" />
          <h1 className="text-3xl font-extrabold tracking-tight text-red-600">Game Time</h1>
          <p className="text-xs text-gray-400 sm:text-sm">Plan tickets, travel, and lodging for your next sports trip.</p>
        </header>

        <section aria-label="Conversation" aria-live="polite" className="max-h-100 min-h-62.5 space-y-4 overflow-y-auto rounded-2xl border border-slate-800 bg-[#1e293b] p-4 shadow-xl sm:p-6 print:hidden">
          {messages.map((message, index) => (
            <div key={`${message.sender}-${index}`} className={`max-w-[85%] rounded-xl p-3 text-sm sm:p-4 ${message.sender === "user" ? "ml-auto rounded-br-none bg-red-600 text-white" : "rounded-bl-none bg-[#334155] text-slate-200"}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{message.text}</ReactMarkdown>
            </div>
          ))}
          {loading && (
            <div className="max-w-[85%] animate-pulse space-y-2 rounded-xl rounded-bl-none border border-red-500/30 bg-[#334155] p-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-red-400">
                <span className="relative flex h-3 w-3"><span className="absolute h-full w-full animate-ping rounded-full bg-red-400 opacity-75" /><span className="relative h-3 w-3 rounded-full bg-red-500" /></span>
                Game Time AI is working...
              </div>
              <p className="text-sm font-medium text-white">{status || LOADING_STEPS[loadingStep]}</p>
            </div>
          )}
        </section>

        <section className="space-y-3 print:hidden">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-400">Try asking:</span>
            {PROMPT_CHIPS.map((chip) => <button key={chip} type="button" onClick={() => void handleSend(chip)} disabled={loading} className="rounded-full border border-slate-700 bg-[#1e293b] px-3 py-1 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-50">{chip}</button>)}
          </div>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <label htmlFor="trip-message" className="sr-only">Message Game Time</label>
            <input id="trip-message" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Type your matchup, date, city, or budget..." disabled={loading} autoComplete="off" className="flex-1 rounded-xl border border-slate-700 bg-[#1e293b] px-4 py-3 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500" />
            <button type="submit" disabled={loading || !input.trim()} className="rounded-xl bg-red-600 px-6 py-3 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-50">Send</button>
          </form>
        </section>

        {error && <div role="alert" className="rounded-xl border border-red-800 bg-red-950/80 p-4 text-sm text-red-200 print:hidden"><p className="font-semibold">Request error</p><p className="mt-1 text-xs text-red-300">{error}</p></div>}

        {itinerary && (
          <article className="space-y-4 rounded-2xl border border-slate-800 bg-[#1e293b] p-6 shadow-xl sm:p-8 print:border-none print:bg-white print:p-0 print:text-black print:shadow-none">
            <div className="flex flex-col justify-between gap-3 border-b border-slate-700 pb-3 sm:flex-row sm:items-center">
              <h2 className="text-xl font-bold text-white print:text-black">Your Custom Itinerary</h2>
              <div className="flex flex-wrap gap-2 print:hidden">
                <button onClick={() => void handleCopy()} className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs hover:bg-slate-600">{copied ? "✓ Copied!" : "📋 Copy"}</button>
                <button onClick={handleEmail} className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs hover:bg-slate-600">✉️ Email</button>
                <button onClick={() => void handleShare()} className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs hover:bg-slate-600">📱 Share</button>
                <button onClick={() => window.print()} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold hover:bg-red-700">🖨️ PDF</button>
              </div>
            </div>
            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900 p-6 text-slate-100 print:border-none print:bg-white print:p-0 print:text-black">
              <div className="prose prose-invert max-w-none prose-table:w-full prose-table:border-collapse prose-th:border prose-th:border-slate-700 prose-th:bg-slate-800 prose-th:p-3 prose-td:border prose-td:border-slate-700 prose-td:p-3 print:prose-not-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{itinerary}</ReactMarkdown>
              </div>
            </div>
          </article>
        )}
      </div>
    </main>
  );
}
