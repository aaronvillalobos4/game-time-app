"use client";

import { useState } from "react";
import { useChat, UIMessage } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";

interface ItineraryChatProps {
  initialItinerary: string | null;
}

export default function ItineraryChat({ initialItinerary }: ItineraryChatProps) {
  const [input, setInput] = useState("");
  
  const { messages, sendMessage, status, error } = useChat({
    transport: new DefaultChatTransport({
      api: "https://game-time-f7qt.onrender.com/api/chat",
      body: {
        currentItinerary: initialItinerary,
      },
    }),
    onError: (err) => {
      console.error("ItineraryChat error:", err);
    },
  });

  const isLoading = status === "submitted" || status === "streaming";

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    sendMessage({ text: input });
    setInput("");
  };

  return (
    <div className="w-full max-w-3xl mx-auto bg-[#1e293b] rounded-2xl border border-slate-800 p-6 shadow-xl text-left space-y-4">
      <h3 className="text-xl font-bold text-white border-b border-slate-700 pb-3">
        Refine Your Trip
      </h3>

      {/* Message History Container */}
      <div className="flex flex-col space-y-3 max-h-96 overflow-y-auto pr-2">
        {messages.length === 0 && (
          <p className="text-xs text-slate-400 italic">
            Have questions or want to make changes? Ask to swap flight times, lower hotel tier, or adjust total budget.
          </p>
        )}

        {messages.map((m: UIMessage) => (
          <div
            key={m.id}
            className={`p-3.5 rounded-xl text-sm leading-relaxed max-w-[85%] ${
              m.role === "user"
                ? "bg-red-600 text-white self-end rounded-br-none"
                : "bg-[#334155] text-slate-100 self-start rounded-bl-none border border-slate-700"
            }`}
          >
            <div className="text-[10px] uppercase font-semibold tracking-wider text-slate-300 mb-1">
              {m.role === "user" ? "You" : "Game Time Assistant"}
            </div>
            <p className="whitespace-pre-wrap">
              {m.parts
                .filter((part) => part.type === "text")
                .map((part) => part.text)
                .join("")}
            </p>
          </div>
        ))}

        {/* Display inline error notice if connection fails */}
        {error && (
          <div className="p-3 bg-red-950/60 border border-red-800 rounded-xl text-xs text-red-300">
            Failed to communicate with the assistant. Please try again.
          </div>
        )}
      </div>

      {/* Input Form */}
      <form onSubmit={handleFormSubmit} className="flex gap-2 pt-2 border-t border-slate-800">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g., Switch hotel to one closer to venue..."
          className="flex-1 bg-[#334155] border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-red-500"
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center min-w-[80px]"
        >
          {isLoading ? (
            <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          ) : (
            "Send"
          )}
        </button>
      </form>
    </div>
  );
}