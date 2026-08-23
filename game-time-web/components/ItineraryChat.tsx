"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ItineraryChatProps {
  initialItinerary?: string | null;
  currentItinerary?: string | null;
}

export default function ItineraryChat({ initialItinerary, currentItinerary }: ItineraryChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeItinerary = currentItinerary || initialItinerary || "";

  const quickPrompts = [
    "Lower hotel tier",
    "Find flights with no layovers",
    "Add budget dining options",
    "Find sports bars near stadium",
  ];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || loading) return;

    const userMessage: Message = { role: "user", content: messageText };
    const updatedMessages = [...messages, userMessage];
    
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("https://game-time-f7qt.onrender.com/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: updatedMessages,
          currentItinerary: activeItinerary,
        }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      const replyText = typeof data.content === "string" ? data.content : JSON.stringify(data.content);

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: replyText || "I've reviewed your request." },
      ]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I couldn't refine your trip right now. Please try sending your message again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 mt-8 shadow-xl text-left">
      <div className="mb-4">
        <h3 className="text-xl font-bold text-white">Refine Your Trip</h3>
        <p className="text-sm text-slate-400 mt-1">
          Ask questions or request updates to adjust flights, hotels, or budget recommendations.
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {quickPrompts.map((prompt, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => sendMessage(prompt)}
            disabled={loading}
            className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-3 py-1.5 rounded-full border border-slate-600 transition-colors disabled:opacity-50"
          >
            + {prompt}
          </button>
        ))}
      </div>

      <div className="space-y-4 mb-4 max-h-96 overflow-y-auto p-3 bg-slate-900/50 rounded-lg border border-slate-800">
        {messages.length === 0 && (
          <div className="text-center text-slate-500 py-6 text-sm">
            No refinements requested yet. Click a suggestion or ask a question below!
          </div>
        )}

        {messages.map((m, index) => (
          <div
            key={index}
            className={`p-4 rounded-xl text-sm leading-relaxed ${
              m.role === "user"
                ? "bg-red-600 text-white ml-auto max-w-lg shadow-md"
                : "bg-slate-700/80 text-slate-100 mr-auto max-w-2xl border border-slate-600"
            }`}
          >
            <div className="text-xs font-semibold uppercase tracking-wider mb-2 opacity-75">
              {m.role === "user" ? "You" : "Game Time Assistant"}
            </div>
            
            {m.role === "user" ? (
              <div className="whitespace-pre-wrap">{m.content}</div>
            ) : (
              <div className="chat-markdown prose prose-invert max-w-none text-slate-100 space-y-2 text-sm">
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({node, ...props}) => <h1 className="text-base font-bold text-white mt-2 mb-1" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-base font-bold text-white mt-2 mb-1" {...props} />,
                    h3: ({node, ...props}) => <h3 className="text-sm font-bold text-white mt-2 mb-1" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc list-inside space-y-1 my-2 pl-2" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal list-inside space-y-1 my-2 pl-2" {...props} />,
                    li: ({node, ...props}) => <li className="text-slate-200" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-semibold text-white" {...props} />,
                    p: ({node, ...props}) => <p className="mb-2 last:mb-0 leading-normal" {...props} />,
                  }}
                >
                  {m.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-slate-400 text-sm p-2">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-ping"></div>
            Refining your itinerary details...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g., Change hotel to one within 5 miles of Kyle Field..."
          disabled={loading}
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 text-sm"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-red-600 text-white px-6 py-2.5 rounded-lg font-semibold hover:bg-red-700 transition-colors disabled:opacity-50 text-sm"
        >
          Send
        </button>
      </form>
    </div>
  );
}