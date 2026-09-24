// Pure PCM encoding/resampling helpers for live mode (Memory Assistant, Stock Voice -
// see docs/adr/0003-clone-speaks-only-in-cloned-voice.md). Kept free of DOM/WebAudio
// globals so they can be unit tested without a browser AudioContext.
//
// The browser mic captures at whatever sample rate the AudioContext runs at (commonly
// 48000 Hz); Gemini Live expects 16-bit PCM, little-endian, mono, 16000 Hz input
// (docs/notes/live-mode.md). Playback audio comes back at 24000 Hz.

export const LIVE_INPUT_SAMPLE_RATE = 16000;
export const LIVE_OUTPUT_SAMPLE_RATE = 24000;

/**
 * Linear-interpolation resample of a mono Float32 buffer from `inputRate` to
 * `outputRate`. Good enough for speech (not a high-quality resampler), and cheap
 * enough to run per mic-capture chunk in the main thread.
 */
export function resampleFloat32(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate || input.length === 0) {
    return input;
  }
  const ratio = inputRate / outputRate;
  const outputLength = Math.round(input.length / ratio);
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio;
    const i0 = Math.floor(srcIndex);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const frac = srcIndex - i0;
    output[i] = input[i0] * (1 - frac) + input[i1] * frac;
  }
  return output;
}

/** Convert a Float32 buffer in [-1, 1] to 16-bit signed PCM, little-endian. */
export function floatTo16BitPCM(input: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i++) {
    const clamped = Math.max(-1, Math.min(1, input[i]));
    const sample = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(i * 2, sample, true /* little-endian */);
  }
  return buffer;
}

/** Convert 16-bit signed little-endian PCM back to Float32 in [-1, 1], for playback. */
export function pcm16ToFloat32(pcm: ArrayBuffer): Float32Array {
  const view = new DataView(pcm);
  const sampleCount = Math.floor(pcm.byteLength / 2);
  const output = new Float32Array(sampleCount);
  for (let i = 0; i < sampleCount; i++) {
    const sample = view.getInt16(i * 2, true);
    output[i] = sample < 0 ? sample / 0x8000 : sample / 0x7fff;
  }
  return output;
}

/** One mic-capture chunk (whatever rate the browser's AudioContext runs at) resampled
 * and encoded to what Gemini Live expects: 16-bit PCM, 16 kHz, mono. */
export function encodeMicChunk(input: Float32Array, inputRate: number): ArrayBuffer {
  const resampled = resampleFloat32(input, inputRate, LIVE_INPUT_SAMPLE_RATE);
  return floatTo16BitPCM(resampled);
}

/** Root-mean-square amplitude of a Float32 buffer, used for the simple "user started
 * talking" heuristic that drives interruption (stop playback when this crosses a
 * threshold). Not a VAD model - good enough to react to a mic that's clearly live. */
export function rmsAmplitude(input: Float32Array): number {
  if (input.length === 0) return 0;
  let sumSquares = 0;
  for (let i = 0; i < input.length; i++) {
    sumSquares += input[i] * input[i];
  }
  return Math.sqrt(sumSquares / input.length);
}
