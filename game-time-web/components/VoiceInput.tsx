"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { VoiceSession, type VoiceState } from "../lib/voice-session";

const subscribe = () => () => {};
const supportedSnapshot = () => Boolean(window.isSecureContext && typeof navigator.mediaDevices?.getUserMedia === "function" && typeof window.RTCPeerConnection === "function");
const serverSnapshot = () => false;

export default function VoiceInput({ endpoint, onTurn, onActiveChange, disabled }: {
  endpoint: string;
  onTurn: (text: string) => Promise<string | undefined>;
  onActiveChange: (active: boolean) => void;
  disabled: boolean;
}) {
  const supported = useSyncExternalStore(subscribe, supportedSnapshot, serverSnapshot);
  const [state, setState] = useState<VoiceState>("idle");
  const [muted, setMuted] = useState(false);
  const [notice, setNotice] = useState("");
  const [transcript, setTranscript] = useState("");
  const session = useRef<VoiceSession | null>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const callbacks = useRef({ onTurn, onActiveChange });
  useEffect(() => { callbacks.current = { onTurn, onActiveChange }; }, [onTurn, onActiveChange]);
  useEffect(() => {
    const stop = () => { session.current?.stop(); session.current = null; };
    const visibility = () => { if (document.hidden) stop(); };
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", stop);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", stop);
      stop();
    };
  }, []);

  const active = state !== "idle";
  const start = () => {
    if (session.current || !audio.current || !supported || disabled) return;
    setNotice(""); setTranscript(""); setMuted(false);
    const connection = new VoiceSession({
      endpoint, audio: audio.current,
      onState: next => {
        setState(next);
        callbacks.current.onActiveChange(next !== "idle");
        if (next === "idle") session.current = null;
      },
      onError: setNotice,
      onTranscript: setTranscript,
      onTurn: text => callbacks.current.onTurn(text),
    });
    session.current = connection;
    void connection.start();
  };

  const label = state === "connecting" ? "Connecting…" : muted ? "Microphone muted"
    : state === "speaking" ? "Game Time is speaking" : state === "thinking" ? "Planning your answer…"
    : active ? "Listening to you" : "Talk to Game Time";

  return (
    <div className="space-y-2">
      <audio ref={audio} autoPlay className="hidden" />
      <button type="button" onClick={active ? () => session.current?.interrupt() : start}
        disabled={!supported || (!active && disabled) || state === "connecting"}
        aria-label={active ? "Interrupt Game Time" : "Start voice conversation with Game Time"}
        aria-pressed={active} aria-describedby="voice-status" className="voice-chat-button disabled:opacity-50">
        <span className="voice-chat-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M9 22h6" /></svg></span>
        <span className="voice-chat-copy"><strong>{label}</strong><span>{active ? "Speak naturally. You can interrupt me." : "A real conversation. Just speak and I'll reply."}</span></span>
        <span className="voice-chat-wave" aria-hidden="true"><i /><i /><i /><i /><i /></span>
      </button>
      {active && <div className="voice-session-controls" role="group" aria-label="Voice conversation controls">
        <button type="button" disabled={state === "connecting"} aria-pressed={muted} onClick={() => {
          const next = !muted; session.current?.setMuted(next); setMuted(next);
        }}>{muted ? "Unmute microphone" : "Mute microphone"}</button>
        <button type="button" disabled={state === "connecting"} onClick={() => session.current?.interrupt()}>Interrupt</button>
        <button type="button" className="voice-end" onClick={() => session.current?.stop()}>End voice chat</button>
      </div>}
      <p id="voice-status" role="status" className="text-xs text-slate-400">
        {!supported ? "Voice needs a supported browser and a secure connection. You can still type below."
          : notice || (active ? (muted ? "Your microphone is off. You can still hear replies." : "Your spoken messages send automatically. Answers and booking options appear in chat.")
            : "AI-generated voice. Starting sends microphone audio to OpenAI for this conversation. English voice chat.")}
      </p>
      {active && transcript && <p className="voice-transcript"><span>You said:</span> {transcript}</p>}
    </div>
  );
}
