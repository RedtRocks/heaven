// Pure logic for driving the 3D face's speech, kept free of DOM/Three.js/TalkingHead
// so it can be unit tested without a browser or WebGL context.

/**
 * HTTP statuses that mean "the /voice/speak endpoint isn't available yet",
 * as opposed to a transient server error. On these we fall back to
 * silent, word-timed lip-sync instead of retrying or surfacing a hard error.
 */
const VOICE_UNAVAILABLE_STATUSES = new Set([404, 501, 503]);

export function isVoiceUnavailableStatus(status: number): boolean {
  return VOICE_UNAVAILABLE_STATUSES.has(status);
}

export interface WordTiming {
  words: string[];
  wtimes: number[];
  wdurations: number[];
  totalMs: number;
}

/**
 * Estimate per-word start times and durations for text with no real audio,
 * so TalkingHead's own English lip-sync module can drive the mouth against
 * a silent audio buffer of matching length. This is a rough approximation
 * (average speaking pace), good enough for a "voice not set up yet" fallback.
 */
export function estimateWordTimings(
  text: string,
  msPerWord = 260,
  gapMs = 40
): WordTiming {
  const words = text.trim().split(/\s+/).filter(Boolean);
  const wtimes: number[] = [];
  const wdurations: number[] = [];
  let t = 0;
  for (const word of words) {
    // Slightly longer duration for longer words, capped so it stays plausible.
    const duration = Math.min(600, Math.max(120, msPerWord * (0.5 + word.length / 8)));
    wtimes.push(t);
    wdurations.push(duration);
    t += duration + gapMs;
  }
  return { words, wtimes, wdurations, totalMs: t };
}
