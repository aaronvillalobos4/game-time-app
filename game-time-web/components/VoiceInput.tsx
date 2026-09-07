"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};
type RecognitionConstructor = new () => Recognition;

function recognitionConstructor() {
  const browser = window as typeof window & {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
}

const subscribe = () => () => {};
const supportedSnapshot = () => Boolean(window.isSecureContext && recognitionConstructor());
const serverSnapshot = () => false;

const errors: Record<string, string> = {
  "not-allowed": "Microphone access was denied. Allow it in your browser's site settings, or type your message.",
  "service-not-allowed": "Your browser has disabled speech recognition. You can still type your message.",
  "audio-capture": "No microphone is available. Check your microphone connection and try again.",
  "no-speech": "I didn't catch any speech. Try again or type your message.",
  network: "Voice recognition couldn't connect. Check your connection or type your message.",
  "language-not-supported": "English speech recognition isn't available in this browser. Please type your message.",
};

export default function VoiceInput({ value, onChange, active, onActiveChange, disabled }: {
  value: string;
  onChange: (text: string) => void;
  active: boolean;
  onActiveChange: (active: boolean) => void;
  disabled: boolean;
}) {
  const supported = useSyncExternalStore(subscribe, supportedSnapshot, serverSnapshot);
  const recognitionRef = useRef<Recognition | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => () => {
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    if (recognition) {
      recognition.onresult = recognition.onerror = recognition.onend = null;
      recognition.abort();
    }
  }, []);

  const toggle = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }
    if (disabled || !supported) return;
    const Constructor = recognitionConstructor();
    if (!Constructor) return;
    const recognition = new Constructor();
    const prefix = value.trim();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognitionRef.current = recognition;
    let failed = false;
    let heardSpeech = false;

    recognition.onresult = (event) => {
      if (recognitionRef.current !== recognition) return;
      const transcript = Array.from(event.results, (result) => result[0]?.transcript ?? "").join(" ").trim();
      heardSpeech = Boolean(transcript);
      const combined = [prefix, transcript].filter(Boolean).join(" ");
      onChange(combined.slice(0, 1_000));
      if (combined.length >= 1_000) {
        setNotice("Message limit reached. Review your text, then send it.");
        recognition.stop();
      }
    };
    recognition.onerror = (event) => {
      if (recognitionRef.current !== recognition) return;
      failed = true;
      setNotice(errors[event.error] ?? "Voice input stopped. Review your text or try again.");
      recognitionRef.current = null;
      recognition.onresult = recognition.onerror = recognition.onend = null;
      recognition.abort();
      onActiveChange(false);
    };
    recognition.onend = () => {
      if (recognitionRef.current !== recognition) return;
      recognitionRef.current = null;
      onActiveChange(false);
      if (!failed) setNotice(heardSpeech ? "Review your message, then press Send." : "No speech captured. Try again or type your message.");
    };
    setNotice("Allow microphone access if prompted, then speak. Tap Stop when finished.");
    onActiveChange(true);
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      recognition.onresult = recognition.onerror = recognition.onend = null;
      recognition.abort();
      onActiveChange(false);
      setNotice("Couldn't start voice input. Check microphone permissions or type your message.");
    }
  };

  return (
    <div className="space-y-1">
      <button type="button" onClick={toggle} disabled={!supported || (disabled && !active)} aria-pressed={active} aria-describedby="voice-status" className={`rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-50 ${active ? "border-red-400 bg-red-600 text-white" : "border-slate-600 bg-slate-800 text-slate-200 hover:bg-slate-700"}`}>
        {active ? "⏹ Stop microphone" : "🎙️ Speak your message"}
      </button>
      <p id="voice-status" role="status" className="text-xs text-slate-400">
        {!supported ? "Voice input isn't available in this browser. You can still type below." : notice || "Dictate in English, review the text, then send. Your browser may process audio through its speech service."}
      </p>
    </div>
  );
}
