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
    <div className="space-y-2">
      <button type="button" onClick={toggle} disabled={!supported || (disabled && !active)} aria-label={active ? "Stop microphone" : "Talk to Game Time — dictate a message"} aria-pressed={active} aria-describedby="voice-status" className="voice-chat-button disabled:opacity-50">
        <span className="voice-chat-icon" aria-hidden="true">
          {active ? <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="3" /></svg> : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M9 22h6" /></svg>}
        </span>
        <span className="voice-chat-copy"><strong>{active ? "Microphone on" : "Talk to Game Time"}</strong><span>{active ? "Tap to stop recording" : "Speak your plans. We'll help with the rest."}</span></span>
        <span className="voice-chat-wave" aria-hidden="true"><i /><i /><i /><i /><i /></span>
      </button>
      <p id="voice-status" role="status" className="text-xs text-slate-400">
        {!supported ? "Voice input isn't available in this browser. You can still type below." : notice || "Dictate in English, review the text, then send. Your browser may process audio through its speech service."}
      </p>
    </div>
  );
}
