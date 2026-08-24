"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const PROMPT_CHIPS = [
  "Mavs @ Celtics on March 14 from Austin, TX with $1200 budget",
  "Cowboys in Dallas on Oct 12 leaving from Houston with $1000 budget",
  "Missouri State @ Texas A&M on Sept 5 from College Station, TX under $700",
];

const FALLBACK_LOADING_MESSAGES = [
  "Estimate wait time five minutes...",
  "Scouting ticket prices & stadium sections...",
  "Searching flight routes & travel schedules...",
  "Scouting highly-rated hotels near the venue...",
  "Synthesizing your custom itinerary & budget breakdown...",
  "Finalizing details (almost ready)...",
];

export default function Home() {
  const [messages, setMessages] = useState<Array<{ sender: "user" | "bot"; text: string }>>([
    {
      sender: "bot",
      text: "Welcome to Game Time! What game do you want to go see?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [slots, setSlots] = useState<{
    event?: string | null;
    date?: string | null;
    departure_city?: string | null;
    budget?: number | null;
  }>({});
  const [itinerary, setItinerary] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Inside Home component in page.tsx:
  const [statusMessage, setStatusMessage] = useState("");
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0);

  const PROGRESSIVE_LOADING_STEPS = [
    "🎟️ Scouting ticket options & stadium seating...",
    "✈️ Comparing flight schedules & airline rates...",
    "🏨 Checking top-rated hotels near the arena...",
    "📊 Verifying prices against your budget...",
    "📝 Formatting your custom weekend schedule..."
  ];

  // Cycle status messages every 6 seconds if loading
  useEffect(() => {
    if (!loading) return;

    const interval = setInterval(() => {
      setLoadingMsgIndex((prev) => (prev + 1) % PROGRESSIVE_LOADING_STEPS.length);
    }, 6000);

    return () => clearInterval(interval);
  }, [loading]);

  const handleSend = async (userText: string) => {
    if (!userText.trim() || loading) return;

    const newMessages = [...messages, { sender: "user" as const, text: userText }];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setErrorMsg(null);

    try {
      // 1. Send input to intent parser
      const parseRes = await fetch("https://game-time-f7qt.onrender.com/api/parse-intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText, current_slots: slots }),
      });

      if (!parseRes.ok) {
        throw new Error(`Parse endpoint error: ${parseRes.statusText}`);
      }

      // Inside handleSend in page.tsx
      const parseData = await parseRes.json();
      const updatedSlots = parseData.slots;
      setSlots(updatedSlots);

      // STOP EXECUTION if budget or any other slot is missing
      if (!parseData.is_complete) {
        setMessages([
          ...newMessages,
          { sender: "bot", text: parseData.follow_up_question },
        ]);
        setLoading(false);
        return; // Execution halts here until user answers
      }

// Proceed to stream ONLY when parseData.is_complete is true

      // 2. Slots complete: trigger the CrewAI pipeline
      setMessages([
        ...newMessages,
        {
          sender: "bot",
          text: `Got all the details! Scouting tickets, flights, and hotels for ${updatedSlots.event} on ${updatedSlots.date}...`,
        },
      ]);

      const streamRes = await fetch("https://game-time-f7qt.onrender.com/api/itinerary-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: updatedSlots.event,
          date: updatedSlots.date,
          departure_city: updatedSlots.departure_city,
          budget: updatedSlots.budget,
        }),
      });

      if (!streamRes.ok) {
        const errText = await streamRes.text();
        throw new Error(`Server returned status ${streamRes.status}: ${errText}`);
      }

      if (!streamRes.body) {
        throw new Error("No readable stream received from server.");
      }

      const reader = streamRes.body.getReader();
      const decoder = new TextDecoder("utf-8");
      setItinerary("");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const events = chunk.split("\n\n");

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue;

          if (eventBlock.includes("[DONE]")) continue;

          const line = eventBlock.trim();
          if (line.startsWith("data: ")) {
            const rawData = line.replace("data: ", "").trim();
            try {
              const parsed = JSON.parse(rawData);
              if (parsed.type === "status") {
                // Update status bar or temporary loading message
                setStatusMessage(parsed.content);
              } else if (parsed.type === "step") {
                // Append step card (Tickets, Flights, Hotels, or Itinerary) directly into chat
                setMessages((prev) => [
                  ...prev,
                  {
                    sender: "bot",
                    text: `### ${parsed.step_name}\n\n${parsed.content}`,
                  },
                ]);
              }
            } catch (err) {
              console.error("Error parsing stream event:", err);
            }
          }
        }
      }
    } catch (err: any) {
      console.error("Error in conversational flow:", err);
      setErrorMsg(err.message || "Failed to process request. Please check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#0f172a] text-white flex flex-col items-center p-6">
      <div className="w-full max-w-3xl space-y-6 my-4">
        
        {/* Header / Brand Logo */}
        <div className="flex flex-col items-center justify-center gap-2 text-center">
          <Image
            src="/logo.png"
            alt="Game Time Logo"
            width={100}
            height={100}
            priority
            className="h-auto w-auto max-h-20 object-contain"
          />
          <h1 className="text-3xl font-extrabold tracking-tight text-red-600">
            Game Time
          </h1>
          <p className="text-gray-400 text-xs sm:text-sm">
            Chat to plan your complete sports trip itinerary.
          </p>
        </div>

        {/* Chat Stream Window */}
        {/* Inside Chat History Window */}
        <div className="bg-[#1e293b] p-4 sm:p-6 rounded-2xl border border-slate-800 space-y-4 min-h-62.5 max-h-100 overflow-y-auto shadow-xl">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`p-3 sm:p-4 rounded-xl text-sm max-w-[85%] ${
                m.sender === "user"
                  ? "bg-red-600 ml-auto text-white rounded-br-none"
                  : "bg-[#334155] text-slate-200 rounded-bl-none"
              }`}
            >
              {m.text}
            </div>
          ))}

          {/* Active Loading Animation Card */}
          {loading && (
            <div className="bg-[#334155] text-slate-200 p-4 rounded-xl rounded-bl-none max-w-[85%] space-y-2 border border-red-500/30 animate-pulse">
              <div className="flex items-center gap-2 text-xs font-semibold text-red-400">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                </span>
                Game Time AI Working...
              </div>
              <p className="text-sm text-white font-medium">
                {statusMessage || PROGRESSIVE_LOADING_STEPS[loadingMsgIndex]}
              </p>
              <p className="text-[11px] text-slate-400">
                This usually takes 30-45 seconds while agents scrape live pricing.
              </p>
            </div>
          )}
        </div>

        {/* One-Shot Prompt Chips */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-400">Try a quick sample trip:</p>
          <div className="flex flex-wrap gap-2">
            {PROMPT_CHIPS.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(chip)}
                disabled={loading}
                className="text-xs bg-[#1e293b] hover:bg-slate-700 text-slate-300 py-2 px-3 rounded-xl border border-slate-700 transition-colors text-left disabled:opacity-50"
              >
                + {chip}
              </button>
            ))}
          </div>
        </div>

        {/* Input Controls */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your matchup, date, city, or budget..."
            disabled={loading}
            className="flex-1 bg-[#1e293b] border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-bold px-6 py-3 rounded-xl transition-colors text-sm"
          >
            Send
          </button>
        </form>

        {/* Error Display */}
        {errorMsg && (
          <div className="bg-red-950/80 border border-red-800 text-red-200 p-4 rounded-xl text-sm text-left">
            <p className="font-semibold">Request Error:</p>
            <p className="text-xs mt-1 text-red-300">{errorMsg}</p>
          </div>
        )}

        {/* Output Itinerary Display */}
        {itinerary && (
          <div className="bg-[#1e293b] p-6 sm:p-8 rounded-2xl border border-slate-800 text-left space-y-4 shadow-xl">
            <h2 className="text-xl font-bold text-white border-b border-slate-700 pb-3 flex items-center justify-between">
              <span>Your Custom Itinerary</span>
            </h2>
            <div className="prose prose-invert max-w-none text-slate-200 text-sm leading-relaxed prose-headings:text-white prose-a:text-red-400 prose-table:border-collapse prose-th:bg-slate-800 prose-th:p-2 prose-td:p-2 prose-td:border-b prose-td:border-slate-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{itinerary}</ReactMarkdown>
            </div>
          </div>
        )}

      </div>
    </main>
  );
}

