"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Script from "next/script";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const PROGRESSIVE_LOADING_STEPS = [
  "🎟️ Scouting ticket options & stadium seating...",
  "✈️ Comparing flight schedules & airline rates...",
  "🏨 Checking top-rated hotels near the arena...",
  "📊 Verifying prices against your budget...",
  "📝 Formatting your custom weekend schedule..."
];

const PROMPT_CHIPS = [
  "🏈 Cowboys vs Eagles in Dallas",
  "⚾ Astros vs Rangers in Houston",
  "🏀 Lakers in LA with $1500 budget",
  "🏒 Golden Knights in Vegas flying from Austin"
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
    needs_flight?: boolean | null;
    departure_city?: string | null;
    budget?: number | null;
  }>({});
  const [itinerary, setItinerary] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0);
  const [copied, setCopied] = useState(false);

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
      const parseRes = await fetch("https://game-time-f7qt.onrender.com/api/parse-intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText, current_slots: slots }),
      });

      if (!parseRes.ok) {
        throw new Error(`Parse endpoint error: ${parseRes.statusText}`);
      }

      const parseData = await parseRes.json();
      const updatedSlots = parseData.slots;
      setSlots(updatedSlots);

      if (!parseData.is_complete) {
        setMessages([
          ...newMessages,
          { sender: "bot", text: parseData.follow_up_question },
        ]);
        setLoading(false);
        return;
      }

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
          departure_city: updatedSlots.departure_city || "Local",
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

      let buffer = "";
      let fullItineraryText = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const eventBlock of events) {
          const line = eventBlock.trim();
          if (!line || line.includes("[DONE]")) continue;

          // Extract text payload whether line starts with "data: " or is raw SSE
          const rawData = line.startsWith("data: ") ? line.replace("data: ", "").trim() : line;
          let contentToAppend = "";

          try {
            const parsed = JSON.parse(rawData);
            if (parsed.type === "status") {
              setStatusMessage(parsed.content || "");
              continue;
            }
            contentToAppend = parsed.content || parsed.text || parsed.result || rawData;
          } catch {
            contentToAppend = rawData;
          }

          if (contentToAppend) {
            fullItineraryText += `\n\n${contentToAppend}`;
            const cleanText = fullItineraryText.trim();
            setItinerary(cleanText);

            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.sender === "bot" && last.text.startsWith("Got all the details!")) {
                return [...prev, { sender: "bot", text: contentToAppend }];
              }
              return [...prev, { sender: "bot", text: contentToAppend }];
            });
          }
        }
      }
    } catch (err: any) {
      console.error("Error in conversational flow:", err);
      setErrorMsg(err.message || "Failed to process request. Please check backend connection.");
    } finally {
      setLoading(false);
      setStatusMessage("");
    }
  };

  const handleChipClick = (chipText: string) => {
    if (loading) return;
    setInput(chipText);
    handleSend(chipText);
  };

  const handlePrint = () => {
    window.print();
  };

  const handleCopy = () => {
    if (!itinerary) return;
    navigator.clipboard.writeText(itinerary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleEmail = () => {
    if (!itinerary) return;
    const subject = encodeURIComponent(`Game Time Itinerary: ${slots.event || "Sports Trip"}`);
    const body = encodeURIComponent(itinerary);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  const handleShare = async () => {
    if (!itinerary) return;
    if (navigator.share) {
      try {
        await navigator.share({
          title: `Game Time Itinerary: ${slots.event || "Sports Trip"}`,
          text: itinerary,
        });
      } catch (err) {
        console.error("Share failed:", err);
      }
    } else {
      handleCopy();
    }
  };

  return (
    <main className="min-h-screen bg-[#0f172a] text-white flex flex-col items-center p-6 print:p-0 print:bg-white print:text-black">
      <Script
        strategy="afterInteractive"
        src="https://www.googletagmanager.com/gtag/js?id=G-CP8PCZ4F12"
      />
      <Script
        id="google-analytics"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-CP8PCZ4F12');
          `,
        }}
      />

      <div className="w-full max-w-3xl space-y-6 my-4">

        <div className="flex flex-col items-center justify-center gap-2 text-center print:hidden">
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

        <div className="bg-[#1e293b] p-4 sm:p-6 rounded-2xl border border-slate-800 space-y-4 min-h-[250px] max-h-[400px] overflow-y-auto shadow-xl print:hidden">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`p-3 sm:p-4 rounded-xl text-sm max-w-[85%] ${
                m.sender === "user"
                  ? "bg-red-600 ml-auto text-white rounded-br-none"
                  : "bg-[#334155] text-slate-200 rounded-bl-none"
              }`}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ node, ...props }) => (
                    <a {...props} target="_blank" rel="noopener noreferrer" className="text-red-400 underline hover:text-red-300 font-medium" />
                  )
                }}
              >
                {m.text}
              </ReactMarkdown>
            </div>
          ))}

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

        <div className="space-y-3 print:hidden">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 font-medium">Try asking:</span>
            {PROMPT_CHIPS.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleChipClick(chip)}
                disabled={loading}
                className="bg-[#1e293b] hover:bg-slate-700 hover:border-slate-500 text-slate-300 border border-slate-700/60 rounded-full px-3 py-1 text-xs transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed select-none"
              >
                {chip}
              </button>
            ))}
          </div>

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
        </div>

        {errorMsg && (
          <div className="bg-red-950/80 border border-red-800 text-red-200 p-4 rounded-xl text-sm text-left print:hidden">
            <p className="font-semibold">Request Error:</p>
            <p className="text-xs mt-1 text-red-300">{errorMsg}</p>
          </div>
        )}

        {itinerary && (
          <div className="bg-[#1e293b] p-6 sm:p-8 rounded-2xl border border-slate-800 text-left space-y-4 shadow-xl print:bg-white print:text-black print:border-none print:shadow-none print:p-0">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-700 pb-3 gap-3 print:border-black">
              <h2 className="text-xl font-bold text-white print:text-black">
                Your Custom Itinerary
              </h2>

              <div className="flex flex-wrap gap-2 print:hidden">
                <button
                  onClick={handleCopy}
                  className="bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium py-1.5 px-3 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  {copied ? "✓ Copied!" : "📋 Copy"}
                </button>
                <button
                  onClick={handleEmail}
                  className="bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium py-1.5 px-3 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  ✉️ Email
                </button>
                <button
                  onClick={handleShare}
                  className="bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium py-1.5 px-3 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  📱 Share / Text
                </button>
                <button
                  onClick={handlePrint}
                  className="bg-red-600 hover:bg-red-700 text-white text-xs font-semibold py-1.5 px-3 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  🖨️ PDF
                </button>
              </div>
            </div>

            <div className="prose prose-invert max-w-none text-slate-200 text-sm leading-relaxed prose-headings:text-white prose-a:text-red-400 prose-table:border-collapse prose-th:bg-slate-800 prose-th:p-2 prose-td:p-2 prose-td:border-b prose-td:border-slate-700 print:prose:text-black print:prose-headings:text-black print:prose-a:text-red-700 print:prose-th:bg-gray-200 print:prose-td:border-gray-300">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ node, ...props }) => (
                    <a {...props} target="_blank" rel="noopener noreferrer" className="text-red-400 underline hover:text-red-300 font-medium print:text-red-700" />
                  )
                }}
              >
                {itinerary}
              </ReactMarkdown>
            </div>
          </div>
        )}

      </div>
    </main>
  );
}