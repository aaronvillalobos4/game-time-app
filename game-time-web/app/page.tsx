"use client";

import Image from "next/image";
import Script from "next/script";
import { FormEvent, useEffect, useRef, useState } from "react";
import TripMarkdown from "../components/TripMarkdown";
import VoiceInput from "../components/VoiceInput";
import SportsTicker from "../components/SportsTicker";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://game-time-f7qt.onrender.com";
const INITIAL_MESSAGE = "Welcome to Game Time! Ask me about game dates, the best matchups this month, venues, or travel ideas. We'll find your game and build a custom itinerary based on your budget.";
const LOADING_STEPS = [
  "🎟️ Scouting ticket options and stadium seating...",
  "✈️ Comparing flight schedules and airline rates...",
  "🏨 Checking top-rated hotels near the arena...",
  "📊 Verifying prices against your budget...",
  "📝 Formatting your custom trip itinerary...",
];
const PROMPT_CHIPS = [
  "What are the top college football games to attend this month?",
  "Which airport should I fly into for a game at Kyle Field?",
  "Show me the Texas A&M Aggies football schedule",
];

type Message = { sender: "user" | "bot"; text: string; id?: string; kind?: "itinerary" };
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

function conversationHistory(messages: Message[]) {
  let remaining = 40_000;
  const recent = [];
  for (const message of messages.slice(-20).reverse()) {
    const content = message.text.slice(0, Math.min(8_000, remaining));
    if (!content) break;
    recent.push({ role: message.sender === "user" ? "user" : "assistant", content });
    remaining -= content.length;
  }
  return recent.reverse();
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([{ sender: "bot", text: INITIAL_MESSAGE }]);
  const [input, setInput] = useState("");
  const [voiceActive, setVoiceActive] = useState(false);
  const [slots, setSlots] = useState<TripSlots>({});
  const [activeItinerary, setActiveItinerary] = useState<{ id: string; text: string; trip: TripSlots } | null>(null);
  const itinerary = activeItinerary?.text ?? null;
  const conversationRef = useRef<HTMLElement>(null);
  const followLatestRef = useRef(true);
  const [loading, setLoading] = useState(false);
  const sendingRef = useRef(false);
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

  useEffect(() => {
    const panel = conversationRef.current;
    if (panel && followLatestRef.current) panel.scrollTop = panel.scrollHeight;
  }, [messages, loading]);

  const addBotMessage = (text: string) => {
    setMessages((current) => [...current, { sender: "bot", text }]);
  };

  const generateItinerary = async (trip: TripSlots, revisionRequest: string, revisionContext: string) => {
    if (!trip.event || !trip.date || trip.budget == null) {
      throw new Error("The trip was marked complete without all required details.");
    }

    addBotMessage(`${itinerary ? "Updating" : "Building"} your itinerary for ${trip.event} on ${trip.date}...`);
    const response = await fetch(`${API_URL}/api/itinerary-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event: trip.event,
        date: trip.date,
        departure_city: trip.departure_city || "Local",
        budget: trip.budget,
        current_itinerary: itinerary?.slice(0, 20_000) ?? null,
        revision_request: revisionRequest,
        revision_context: revisionContext,
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
    let streamFinished = false;
    const itineraryId = crypto.randomUUID();
    setMessages((current) => [...current, { sender: "bot", text: "", id: itineraryId, kind: "itinerary" }]);

    const processEvent = (block: string) => {
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n")
        .trim();
      if (data === "[DONE]") {
        streamFinished = true;
        return;
      }
      if (!data) return;

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
        const streamedText = completeText.trim();
        setMessages((current) => current.map((message) => message.id === itineraryId ? { ...message, text: streamedText } : message));
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() ?? "";
        blocks.forEach(processEvent);
        if (done) break;
      }
      if (buffer.trim()) processEvent(buffer);
      if (!streamFinished) throw new Error("The itinerary connection ended early. Please try again.");
      if (!completeText.trim()) throw new Error("The agents finished without returning an itinerary.");
      setActiveItinerary({ id: itineraryId, text: completeText.trim(), trip });
      setCopied(false);
    } catch (caught) {
      // Keep the last successful itinerary available if a revision fails.
      setMessages((current) => current.filter((message) => message.id !== itineraryId));
      await reader.cancel().catch(() => undefined);
      throw caught;
    } finally {
      reader.releaseLock();
    }
  };

  const handleSend = async (rawText: string, fromVoice = false): Promise<string | undefined> => {
    const text = rawText.trim();
    if (!text || sendingRef.current || (voiceActive && !fromVoice)) return;
    sendingRef.current = true;

    followLatestRef.current = true;
    setMessages((current) => [...current, { sender: "user", text }]);
    setInput("");
    setLoading(true);
    setLoadingStep(0);
    setStatus("Checking your request and looking up event details...");
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/parse-intent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          current_slots: slots,
          history: conversationHistory(messages),
          current_itinerary: itinerary?.slice(0, 20_000) ?? null,
        }),
      });
      if (!response.ok) throw new Error(`Conversation request failed (${response.status}).`);

      const parsed = (await response.json()) as ParseResponse;
      if (parsed.is_reset) {
        setSlots({});
        setActiveItinerary(null);
        setMessages([{ sender: "bot", text: parsed.follow_up_question || INITIAL_MESSAGE }]);
        return parsed.follow_up_question || INITIAL_MESSAGE;
      }

      // The server merges confirmed choices and clears stale dependent details.
      const updatedSlots = parsed.slots ?? slots;
      setSlots(updatedSlots);
      if (parsed.follow_up_question) addBotMessage(parsed.follow_up_question);
      if (!parsed.is_complete) return parsed.follow_up_question ?? undefined;
      await generateItinerary(updatedSlots, text, JSON.stringify([
        ...conversationHistory(messages),
        { role: "assistant", content: parsed.follow_up_question ?? "" },
      ]).slice(-40_000));
      return "Your itinerary is ready in chat, with the game-day plan, budget, and booking options. What would you like to adjust?";
    } catch (caught: unknown) {
      console.error("Game Time error:", caught);
      setError(getErrorMessage(caught));
      return "I couldn't finish that request. Please try again. Your previous trip details are still in chat.";
    } finally {
      setLoading(false);
      sendingRef.current = false;
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
    const subject = encodeURIComponent(`Game Time Itinerary: ${activeItinerary?.trip.event || "Sports Trip"}`);
    window.location.href = `mailto:?subject=${subject}&body=${encodeURIComponent(itinerary)}`;
  };

  const handleShare = async () => {
    if (!itinerary) return;
    if (!navigator.share) return handleCopy();
    try {
      await navigator.share({ title: `Game Time: ${activeItinerary?.trip.event || "Sports Trip"}`, text: itinerary });
    } catch (caught: unknown) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(getErrorMessage(caught));
    }
  };

  return (
    <main className="game-shell min-h-screen text-white print:bg-white print:p-0 print:text-black">
      <div className="stadium-scene print:hidden" aria-hidden="true"><div className="stadium-field" /></div>
      <Script strategy="afterInteractive" src="https://www.googletagmanager.com/gtag/js?id=G-CP8PCZ4F12" />
      <Script id="google-analytics" strategy="afterInteractive">
        {`window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', 'G-CP8PCZ4F12');`}
      </Script>

      <div className="game-content">
        <header className="game-header print:hidden">
          <a href="/" className="game-brand" aria-label="Game Time home"><Image src="/logo.png" alt="" width={64} height={64} priority className="h-12 w-12 object-contain" /><span>GAME<span className="text-sky-400">TIME</span><small>BE THERE FOR IT.</small></span></a>
          <a href="#trip-message" className="header-link">Plan your next trip <span aria-hidden="true">↗</span></a>
        </header>

        <section className="game-hero print:hidden">
          <p className="hero-eyebrow"><span /> YOUR AI SPORTS TRAVEL ASSISTANT</p>
          <h1>The game is calling.<br /><span>Make your way there.</span></h1>
          <p>From the first whistle to the final night. Find your game,<br className="hidden sm:block" /> tickets, flights, and stays — in one conversation.</p>
          <div className="hero-services"><span>01 / Find your game</span><span>02 / Build your trip</span><span>03 / Be there</span></div>
        </section>

        <div className="planner-panel">
        <div className="planner-heading print:hidden"><div><span className="assistant-mark" aria-hidden="true">✦</span><div><h2>Game Time AI</h2><p>Your next great sports story starts here.</p></div></div><span className="assistant-status"><i /> Ready to plan</span></div>

        <section ref={conversationRef} onScroll={() => {
          const panel = conversationRef.current;
          if (panel) followLatestRef.current = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 80;
        }} aria-label="Conversation" aria-live="polite" className="conversation-panel max-h-[60vh] min-h-56 space-y-4 overflow-y-auto p-4 sm:p-6 print:max-h-none print:overflow-visible print:p-0">
          {messages.map((message, index) => message.kind === "itinerary" ? (
            <article key={message.id} aria-label="Trip itinerary" className={`min-w-0 space-y-4 rounded-xl border border-slate-600 bg-slate-900 p-4 sm:p-6 ${message.id === activeItinerary?.id ? "print:border-0 print:bg-white print:p-0 print:text-black" : "print:hidden"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-bold">{message.id === activeItinerary?.id ? "Your Current Itinerary" : message.text ? "Itinerary" : "Building your itinerary..."}</h2>
                {message.id === activeItinerary?.id && (
                  <div className="flex flex-wrap gap-2 print:hidden">
                    <button onClick={() => void handleCopy()} className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs hover:bg-slate-600">{copied ? "Copied!" : "Copy"}</button>
                    <button onClick={handleEmail} className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs hover:bg-slate-600">Email</button>
                    <button onClick={() => void handleShare()} className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs hover:bg-slate-600">Share</button>
                    <button onClick={() => window.print()} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs hover:bg-red-700">PDF</button>
                  </div>
                )}
              </div>
              <p className="text-xs text-slate-400 print:text-gray-600">Game Time may earn a commission when you book through links in this itinerary, at no additional cost to you.</p>
              <TripMarkdown>{message.text}</TripMarkdown>
              {message.id === activeItinerary?.id && <p className="text-sm text-slate-300 print:hidden">Want to make changes? Ask below to adjust your budget, hotel, tickets, or travel.</p>}
            </article>
          ) : (
            <div key={`${message.sender}-${index}`} className={`chat-message min-w-0 max-w-[95%] sm:max-w-[90%] rounded-xl p-3 text-sm sm:p-4 print:hidden ${message.sender === "user" ? "chat-message-user ml-auto text-white" : "chat-message-bot text-slate-200"}`}>
              <p className="message-author">{message.sender === "user" ? "YOU" : "GAME TIME AI"}</p>
              <TripMarkdown>{message.text}</TripMarkdown>
            </div>
          ))}
          {loading && (
            <div className="print:hidden max-w-[85%] animate-pulse space-y-2 rounded-xl rounded-bl-none border border-red-500/30 bg-[#334155] p-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-red-400">
                <span className="relative flex h-3 w-3"><span className="absolute h-full w-full animate-ping rounded-full bg-red-400 opacity-75" /><span className="relative h-3 w-3 rounded-full bg-red-500" /></span>
                Game Time AI is working...
              </div>
              <p className="text-sm font-medium text-white">{status || LOADING_STEPS[loadingStep]}</p>
            </div>
          )}
        </section>

        <section className="chat-composer space-y-3 print:hidden">
          <VoiceInput endpoint={`${API_URL}/api/voice/session`} onTurn={text => handleSend(text, true)} onActiveChange={setVoiceActive} disabled={loading} />
          <form onSubmit={handleSubmit} className="message-form flex gap-2">
            <label htmlFor="trip-message" className="sr-only">Message Game Time</label>
            <input id="trip-message" value={input} onChange={(event) => setInput(event.target.value)} placeholder={itinerary ? "Ask a question or request an itinerary change..." : "Type your matchup, date, city, or budget..."} disabled={loading || voiceActive} maxLength={1000} autoComplete="off" className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-[#1e293b] px-4 py-3 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500" />
            <button type="submit" disabled={loading || voiceActive || !input.trim()} className="rounded-xl bg-red-600 px-6 py-3 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-50">Send</button>
          </form>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-slate-400">Try asking:</span>
            {(itinerary ? ["Lower my total budget to $800", "Replace the hotel with a cheaper option", "Find a hotel closer to the stadium"] : PROMPT_CHIPS).map((chip) => <button key={chip} type="button" onClick={() => void handleSend(chip)} disabled={loading || voiceActive} className="rounded-full border border-slate-700 bg-[#1e293b] px-3 py-1 text-xs text-slate-300 hover:bg-slate-700 disabled:opacity-50">{chip}</button>)}
          </div>
        </section>
        </div>

        <div className="scoreboard-panel print:hidden"><div className="section-caption"><span>AROUND THE LEAGUES</span><span>The next trip starts with a great matchup.</span></div><SportsTicker /></div>
        <footer className="game-footer print:hidden"><span>BIG GAMES. UNFORGETTABLE TRIPS.</span><span>Powered by curiosity. Planned with AI.</span></footer>

        {error && <div role="alert" className="rounded-xl border border-red-800 bg-red-950/80 p-4 text-sm text-red-200 print:hidden"><p className="font-semibold">Request error</p><p className="mt-1 text-xs text-red-300">{error}</p></div>}


      </div>
    </main>
  );
}
