"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { TalkingHead } from "@met4citizen/talkinghead";
import { Lipsync } from "wawa-lipsync";
import { getApiUrl } from "@/lib/api";
import { estimateWordTimings, isVoiceUnavailableStatus } from "@/lib/faceSpeech";

export interface FaceStageHandle {
  /** Make the face speak `text`. Safe to call even if the avatar failed to load. */
  speak: (text: string) => void;
}

type AvatarStatus = "checking" | "loading" | "ready" | "missing" | "error";

const DEFAULT_AVATAR_URL = "/avatar/owner.glb";
const DEV_AVATAR_URL = process.env.NEXT_PUBLIC_DEV_AVATAR_URL;
const MAX_PIXEL_RATIO = 1.5;

const FaceStageCanvas = forwardRef<FaceStageHandle>(function FaceStageCanvas(
  _props,
  ref
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const headRef = useRef<TalkingHead | null>(null);

  // Real-audio lip-sync state (wawa-lipsync analyzing the actual /voice/speak audio).
  const lipsyncRef = useRef<Lipsync | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastVisemeRef = useRef<string | null>(null);
  const mutedRef = useRef(false);

  const [avatarStatus, setAvatarStatus] = useState<AvatarStatus>("checking");
  const [muted, setMuted] = useState(false);
  const [voiceNotSetUp, setVoiceNotSetUp] = useState(false);
  const [fps, setFps] = useState(0);
  const [debug, setDebug] = useState(false);

  useEffect(() => {
    mutedRef.current = muted;
    if (audioElRef.current) audioElRef.current.muted = muted;
  }, [muted]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setDebug(new URLSearchParams(window.location.search).get("debug") === "1");
  }, []);

  // Load the avatar once on mount.
  useEffect(() => {
    let cancelled = false;
    const avatarUrl = DEV_AVATAR_URL || DEFAULT_AVATAR_URL;

    async function load() {
      setAvatarStatus("checking");
      try {
        // HEAD-check first so a missing GLB shows the empty state instead of
        // spinning up a WebGL context and renderer for nothing.
        const head = await fetch(avatarUrl, { method: "HEAD" });
        if (!head.ok) {
          if (!cancelled) setAvatarStatus("missing");
          return;
        }
      } catch {
        if (!cancelled) setAvatarStatus("missing");
        return;
      }

      if (cancelled || !containerRef.current) return;
      setAvatarStatus("loading");

      try {
        const pixelRatio = Math.min(
          typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1,
          MAX_PIXEL_RATIO
        );
        const th = new TalkingHead(containerRef.current, {
          lipsyncModules: ["en"],
          lipsyncLang: "en",
          modelPixelRatio: pixelRatio,
          cameraView: "head",
        });
        await th.showAvatar({
          url: avatarUrl,
          body: "M",
          lipsyncLang: "en",
        });
        if (cancelled) return;
        headRef.current = th;
        setAvatarStatus("ready");
      } catch (err) {
        console.error("Failed to load 3D avatar:", err);
        if (!cancelled) setAvatarStatus("error");
      }
    }

    load();

    return () => {
      cancelled = true;
      stopLipsyncLoop();
      audioElRef.current?.pause();
      headRef.current = null;
    };
  }, []);

  // FPS readout (dev only, ?debug=1).
  useEffect(() => {
    if (!debug) return;
    let frame = 0;
    let last = performance.now();
    let count = 0;
    const loop = (now: number) => {
      count++;
      if (now - last >= 1000) {
        setFps(count);
        count = 0;
        last = now;
      }
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [debug]);

  function stopLipsyncLoop() {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (lastVisemeRef.current && headRef.current) {
      headRef.current.setFixedValue(lastVisemeRef.current, null);
      lastVisemeRef.current = null;
    }
  }

  function driveVisemesFromAudio() {
    const head = headRef.current;
    const lipsync = lipsyncRef.current;
    const audioEl = audioElRef.current;
    if (!head || !lipsync || !audioEl) return;

    lipsync.processAudio();
    const viseme: string = lipsync.viseme;
    const volume = lipsync.features?.volume ?? 0;
    // wawa-lipsync's amplitude scale is quiet for normal speech; boost it a
    // little so the mouth actually opens, while staying within [0, 1].
    const intensity = Math.min(1, Math.max(0.15, volume * 4));

    if (viseme !== lastVisemeRef.current) {
      if (lastVisemeRef.current) {
        head.setFixedValue(lastVisemeRef.current, null);
      }
      lastVisemeRef.current = viseme;
    }
    if (viseme && viseme !== "viseme_sil") {
      head.setFixedValue(viseme, intensity);
    } else if (lastVisemeRef.current) {
      head.setFixedValue(lastVisemeRef.current, null);
    }

    if (!audioEl.paused && !audioEl.ended) {
      rafRef.current = requestAnimationFrame(driveVisemesFromAudio);
    } else {
      stopLipsyncLoop();
    }
  }

  /** Real audio path: play the WAV ourselves and drive visemes from its waveform. */
  function speakWithAudio(arrayBuffer: ArrayBuffer) {
    stopLipsyncLoop();
    audioElRef.current?.pause();

    const blob = new Blob([arrayBuffer], { type: "audio/wav" });
    const url = URL.createObjectURL(blob);
    const audioEl = new Audio(url);
    audioEl.muted = mutedRef.current;
    audioElRef.current = audioEl;

    if (!lipsyncRef.current) {
      lipsyncRef.current = new Lipsync();
    }
    lipsyncRef.current.connectAudio(audioEl);

    audioEl.addEventListener("ended", () => {
      stopLipsyncLoop();
      URL.revokeObjectURL(url);
    });
    audioEl
      .play()
      .then(() => {
        rafRef.current = requestAnimationFrame(driveVisemesFromAudio);
      })
      .catch((err) => {
        console.error("Failed to play speech audio:", err);
      });
  }

  /** Fallback path: no server audio, so drive the mouth from estimated word timing
   * against a silent buffer, using TalkingHead's own English lip-sync module. */
  function speakSilently(text: string) {
    const head = headRef.current;
    if (!head) return;
    const { words, wtimes, wdurations, totalMs } = estimateWordTimings(text);
    if (words.length === 0) return;

    const ctx = new (window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext)();
    const sampleRate = ctx.sampleRate;
    const durationSec = Math.max(0.2, totalMs / 1000 + 0.3);
    const silentBuffer = ctx.createBuffer(
      1,
      Math.ceil(durationSec * sampleRate),
      sampleRate
    );

    head.speakAudio({
      audio: silentBuffer,
      words,
      wtimes,
      wdurations,
    });
  }

  async function speak(text: string) {
    if (avatarStatus !== "ready" || !text.trim()) return;

    try {
      const res = await fetch(getApiUrl("/voice/speak"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (isVoiceUnavailableStatus(res.status)) {
        setVoiceNotSetUp(true);
        speakSilently(text);
        return;
      }
      if (!res.ok) {
        throw new Error(`voice/speak returned ${res.status}`);
      }

      setVoiceNotSetUp(false);
      const arrayBuffer = await res.arrayBuffer();
      speakWithAudio(arrayBuffer);
    } catch (err) {
      console.warn("voice/speak unavailable, falling back to silent lip-sync:", err);
      setVoiceNotSetUp(true);
      speakSilently(text);
    }
  }

  useImperativeHandle(ref, () => ({ speak }));

  return (
    <div className="relative w-full h-64 sm:h-80 rounded-lg overflow-hidden bg-slate-200 dark:bg-slate-800 border border-slate-300 dark:border-slate-600">
      {/* TalkingHead mounts its own <canvas> into this node. */}
      <div
        ref={containerRef}
        className="w-full h-full"
        style={{ display: avatarStatus === "ready" ? "block" : "none" }}
      />

      {avatarStatus === "checking" || avatarStatus === "loading" ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-slate-500 dark:text-slate-400 text-sm">
            Loading 3D face…
          </p>
        </div>
      ) : null}

      {avatarStatus === "missing" ? (
        <div className="absolute inset-0 flex items-center justify-center p-4">
          <div className="text-center max-w-sm">
            <div className="text-4xl mb-2">🧑</div>
            <p className="text-slate-700 dark:text-slate-300 font-medium mb-1">
              No 3D avatar yet
            </p>
            <p className="text-slate-500 dark:text-slate-400 text-sm">
              Create one in Avaturn from your photos, export it as a GLB with
              ARKit/Oculus blendshapes, and place it at{" "}
              <code className="bg-slate-300/50 dark:bg-slate-700/50 px-1 rounded">
                web/public/avatar/owner.glb
              </code>
              . See{" "}
              <code className="bg-slate-300/50 dark:bg-slate-700/50 px-1 rounded">
                docs/notes/face-3d-setup.md
              </code>{" "}
              for step-by-step instructions.
            </p>
          </div>
        </div>
      ) : null}

      {avatarStatus === "error" ? (
        <div className="absolute inset-0 flex items-center justify-center p-4">
          <p className="text-red-600 dark:text-red-400 text-sm text-center">
            Couldn&apos;t load the 3D avatar. Check the browser console for
            details, and that the GLB has ARKit/Oculus blendshapes.
          </p>
        </div>
      ) : null}

      {avatarStatus === "ready" ? (
        <div className="absolute bottom-2 right-2 flex items-center gap-2">
          {voiceNotSetUp && (
            <span className="text-xs bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-100 px-2 py-1 rounded">
              Voice not set up — lips move, no audio
            </span>
          )}
          <button
            type="button"
            onClick={() => setMuted((m) => !m)}
            className="text-xs bg-slate-700/80 text-white px-2 py-1 rounded hover:bg-slate-700"
          >
            {muted ? "Unmute" : "Mute"}
          </button>
        </div>
      ) : null}

      {debug && (
        <div className="absolute top-2 left-2 text-xs font-mono bg-black/60 text-lime-300 px-2 py-1 rounded">
          {fps} fps
        </div>
      )}
    </div>
  );
});

export default FaceStageCanvas;
