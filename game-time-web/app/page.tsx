"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ItineraryChat from "@/components/ItineraryChat";

const FALLBACK_LOADING_MESSAGES = [
  "Estimate wait time five minutes...",
  "Scouting ticket prices & stadium sections...",
  "Searching flight routes & travel schedules...",
  "Scouting highly-rated hotels near the venue...",
  "Synthesizing your custom itinerary & budget breakdown...",
  "Finalizing details (almost ready)...",
];

export default function Home() {
  const [event, setEvent] = useState("");
  const [date, setDate] = useState("");
  const [departureCity, setDepartureCity] = useState("");
  const [budget, setBudget] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0);
  const [itinerary, setItinerary] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

// Cycle through default fallback messages if no live SSE status is received
useEffect(() => {
  // Only exit if we have received an explicit live status message from the SSE backend stream
  if (!loading || statusMessage) return;

  setLoadingMsgIndex(0);

  const interval = setInterval(() => {
    setLoadingMsgIndex((prevIndex) => 
      prevIndex < FALLBACK_LOADING_MESSAGES.length - 1 ? prevIndex + 1 : prevIndex
    );
  }, 5000);

  return () => clearInterval(interval);
}, [loading, statusMessage]);

  const handleGenerate = async (e: React.FormEvent) => {
  e.preventDefault();
  setLoading(true);
  setItinerary("");
  setErrorMsg(null);
  setStatusMessage(""); // Keep empty so the progressive array timer activates right away!

    // Clean currency symbols or formatting from input before sending
    const numericBudget = parseFloat(budget.replace(/[^0-9.]/g, "")) || budget;

    try {
      const response = await fetch("https://game-time-f7qt.onrender.com/api/itinerary-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event,
          date,
          departure_city: departureCity,
          budget: numericBudget,
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Server returned status ${response.status}: ${errText}`);
      }

      // Handle raw JSON response fallback if content-type is non-stream
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await response.json();
        setItinerary(data.itinerary || JSON.stringify(data, null, 2));
        return;
      }

      if (!response.body) {
        throw new Error("No readable stream received from server.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const events = chunk.split("\n\n");

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue;

          if (eventBlock.includes("[DONE]")) {
            setStatusMessage("");
            continue;
          }

          const line = eventBlock.trim();
          if (line.startsWith("data: ")) {
            const rawData = line.replace("data: ", "").trim();

            try {
              const parsed = JSON.parse(rawData);

              if (parsed.type === "status") {
                setStatusMessage(parsed.content);
              } else if (parsed.type === "token") {
                // Functional state updater to prevent dropped tokens during renders
                setItinerary((prev) => (prev || "") + parsed.content);
              } else if (parsed.type === "error") {
                throw new Error(parsed.content);
              }
            } catch (jsonErr) {
              // Fallback for raw text chunking
              setItinerary((prev) => (prev || "") + rawData);
            }
          }
        }
      }
    } catch (err: any) {
      console.error("Error generating itinerary:", err);
      setErrorMsg(
        err.message || "Failed to fetch itinerary. Check backend server connection."
      );
    } finally {
      setLoading(false);
      setStatusMessage("");
    }
  };

  return (
    <main className="min-h-screen bg-[#0f172a] text-white flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-3xl text-center space-y-6 my-8">
        
        {/* Header / Brand Logo */}
        <div className="flex flex-col items-center justify-center gap-3">
          <Image
            src="/logo.png"
            alt="Game Time Logo"
            width={120}
            height={120}
            priority
            className="h-auto w-auto max-h-24 object-contain"
          />
          <h1 className="text-4xl font-extrabold tracking-tight text-red-600">
            Game Time
          </h1>
        </div>

        <p className="text-gray-400 text-sm sm:text-base">
          Plan your complete sports trip itinerary (tickets, flights, hotels).
        </p>

        {/* Form Container */}
        <form onSubmit={handleGenerate} className="bg-[#1e293b] p-6 rounded-2xl shadow-xl border border-slate-800 text-left space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1">
              Game / Event
            </label>
            <input
              type="text"
              value={event}
              onChange={(e) => setEvent(e.target.value)}
              placeholder="e.g. Mavericks @ Celtics"
              className="w-full bg-[#334155] border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">
                Date
              </label>
              <input
                type="text"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                placeholder="mm/dd/yyyy"
                className="w-full bg-[#334155] border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">
                Departure City
              </label>
              <input
                type="text"
                value={departureCity}
                onChange={(e) => setDepartureCity(e.target.value)}
                placeholder="Austin"
                className="w-full bg-[#334155] border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">
                Total Budget
              </label>
              <input
                type="text"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="$1200"
                className="w-full bg-[#334155] border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-bold py-3 rounded-lg transition-colors text-sm flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>{statusMessage || FALLBACK_LOADING_MESSAGES[loadingMsgIndex]}</span>
              </>
            ) : (
              "Generate Custom Itinerary"
            )}
          </button>
        </form>

        {/* Error Feedback Display */}
        {errorMsg && (
          <div className="bg-red-950/80 border border-red-800 text-red-200 p-4 rounded-xl text-sm text-left">
            <p className="font-semibold">Request Error:</p>
            <p className="text-xs mt-1 text-red-300">{errorMsg}</p>
          </div>
        )}

        {/* Streaming Formatted Output */}
        {itinerary && (
          <div className="bg-[#1e293b] p-6 sm:p-8 rounded-2xl border border-slate-800 text-left space-y-4 shadow-xl">
            <h2 className="text-2xl font-bold text-white border-b border-slate-700 pb-3 flex items-center justify-between">
              <span>Your Custom Itinerary</span>
              {loading && (
                <span className="text-xs text-red-400 font-normal animate-pulse">
                  Streaming live...
                </span>
              )}
            </h2>
            <div className="prose prose-invert max-w-none text-slate-200 text-sm leading-relaxed prose-headings:text-white prose-a:text-red-400 prose-table:border-collapse prose-th:bg-slate-800 prose-th:p-2 prose-td:p-2 prose-td:border-b prose-td:border-slate-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{itinerary}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Interactive Refinement Chat Assistant */}
        <div className="mt-8">
          <ItineraryChat />
        </div>

      </div>
    </main>
  );
}