"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getWsUrl } from "@/lib/api";
import { encodeMicChunk, LIVE_OUTPUT_SAMPLE_RATE, pcm16ToFloat32, rmsAmplitude } from "@/lib/liveAudio";

// RMS threshold above which we treat the mic as "the user started talking", and stop
// any assistant audio that's currently playing (a simple client-side barge-in; Gemini
// Live also runs its own server-side interruption detection).
const SPEECH_RMS_THRESHOLD = 0.02;

export interface LiveTranscriptEvent {
  speaker: "user" | "model";
  text: string;
  final: boolean;
}

interface LiveTalkProps {
  onTranscript?: (event: LiveTranscriptEvent) => void;
  onEnded?: (reason: string) => void;
}

type LiveStatus = "idle" | "connecting" | "live" | "error" | "ended";

/**
 * "Talk live" for the Memory Assistant: streams mic audio to /live/assistant over a
 * WebSocket and plays back the model's speech. Stock Voice only - never used on /clone
 * (ADR 0003, docs/notes/live-mode.md).
 */
export default function LiveTalk({ onTranscript, onEnded }: LiveTalkProps) {
  const [status, setStatus] = useState<LiveStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const micContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef(0);
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]);

  const stopPlayback = useCallback(() => {
    for (const source of activeSourcesRef.current) {
      try {
        source.stop();
      } catch {
        // already stopped/ended
      }
    }
    activeSourcesRef.current = [];
    if (playbackContextRef.current) {
      nextPlayTimeRef.current = playbackContextRef.current.currentTime;
    }
  }, []);

  const playChunk = useCallback((pcm: ArrayBuffer) => {
    let ctx = playbackContextRef.current;
    if (!ctx) {
      ctx = new AudioContext({ sampleRate: LIVE_OUTPUT_SAMPLE_RATE });
      playbackContextRef.current = ctx;
      nextPlayTimeRef.current = ctx.currentTime;
    }
    const samples = pcm16ToFloat32(pcm);
    if (samples.length === 0) return;

    const buffer = ctx.createBuffer(1, samples.length, LIVE_OUTPUT_SAMPLE_RATE);
    buffer.getChannelData(0).set(samples);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.onended = () => {
      activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== source);
    };

    const startAt = Math.max(ctx.currentTime, nextPlayTimeRef.current);
    source.start(startAt);
    nextPlayTimeRef.current = startAt + buffer.duration;
    activeSourcesRef.current.push(source);
  }, []);

  const stop = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    micStreamRef.current = null;
    micContextRef.current?.close().catch(() => {});
    micContextRef.current = null;
    stopPlayback();
    playbackContextRef.current?.close().catch(() => {});
    playbackContextRef.current = null;
    setStatus("idle");
  }, [stopPlayback]);

  const start = useCallback(async () => {
    setError(null);
    setStatus("connecting");
    // Set when the server ends the session (error or session_ended). Setup below may
    // still be awaiting mic/worklet; its teardown errors must not replace the
    // server's message, and it must not flip the status back to "live".
    let endedByServer = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;

      const ws = new WebSocket(getWsUrl("/live/assistant"));
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          const msg = JSON.parse(event.data);
          if (msg.type === "transcript") {
            if (msg.speaker === "user") stopPlayback(); // user's own speech interrupts playback
            onTranscript?.({ speaker: msg.speaker, text: msg.text, final: msg.final });
          } else if (msg.type === "session_ended") {
            endedByServer = true;
            stop();
            setStatus("ended");
            onEnded?.(msg.reason);
          } else if (msg.type === "error") {
            endedByServer = true;
            stop();
            setError(msg.message);
            setStatus("error");
          }
        } else {
          playChunk(event.data as ArrayBuffer);
        }
      };
      ws.onerror = () => {
        setError("Live connection failed.");
        setStatus("error");
      };
      ws.onclose = () => {
        setStatus((s) => (s === "error" ? s : "ended"));
      };

      await new Promise<void>((resolve, reject) => {
        ws.addEventListener("open", () => resolve(), { once: true });
        ws.addEventListener("error", () => reject(new Error("WebSocket failed to open")), { once: true });
      });

      const micContext = new AudioContext();
      micContextRef.current = micContext;
      await micContext.audioWorklet.addModule("/live-mic-worklet.js");

      const source = micContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(micContext, "live-mic-processor");
      workletNode.port.onmessage = (e: MessageEvent<Float32Array>) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const chunk = e.data;
        if (rmsAmplitude(chunk) > SPEECH_RMS_THRESHOLD) {
          stopPlayback();
        }
        const pcm = encodeMicChunk(chunk, micContext.sampleRate);
        ws.send(pcm);
      };
      source.connect(workletNode);

      if (endedByServer || ws.readyState !== WebSocket.OPEN) return;
      setStatus("live");
    } catch (err) {
      if (endedByServer) return; // keep the server's explanation
      stop();
      setError(err instanceof Error ? err.message : "Couldn't start live mode.");
      setStatus("error");
    }
  }, [onEnded, onTranscript, playChunk, stop, stopPlayback]);

  useEffect(() => stop, [stop]); // clean up on unmount

  return (
    <div className="flex items-center gap-3">
      {status === "idle" || status === "ended" || status === "error" ? (
        <button
          type="button"
          onClick={start}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700"
        >
          Talk live
        </button>
      ) : (
        <button
          type="button"
          onClick={stop}
          className="text-sm bg-red-600 text-white px-3 py-1.5 rounded hover:bg-red-700"
        >
          {status === "connecting" ? "Connecting…" : "End live call"}
        </button>
      )}
      {status === "live" && <span className="text-xs text-green-600 dark:text-green-400">Live</span>}
      {error && <span className="text-xs text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}
