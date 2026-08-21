"use client";

import { useChat } from "ai/react";

export default function ItineraryChat({ initialItinerary }: { initialItinerary: any }) {
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: "/api/chat", // Pointing to your FastAPI route or proxy
    body: {
      currentItinerary: initialItinerary,
    },
  });

  return (
    <div className="flex flex-col h-full max-w-xl border rounded-lg p-4 bg-gray-900 text-white">
      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`p-3 rounded-md ${
              m.role === "user" ? "bg-blue-600 self-end" : "bg-gray-800 self-start"
            }`}
          >
            <strong>{m.role === "user" ? "You: " : "Game Time Bot: "}</strong>
            {m.content}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={handleInputChange}
          placeholder="Ask to change hotels, update budget, or swap flights..."
          className="flex-1 p-2 border rounded bg-gray-800 text-white focus:outline-none"
        />
        <button type="submit" className="px-4 py-2 bg-blue-600 rounded font-semibold hover:bg-blue-500">
          Send
        </button>
      </form>
    </div>
  );
}