import { describe, expect, it } from "vitest";
import {
  encodeMicChunk,
  floatTo16BitPCM,
  LIVE_INPUT_SAMPLE_RATE,
  pcm16ToFloat32,
  resampleFloat32,
  rmsAmplitude,
} from "./liveAudio";

describe("resampleFloat32", () => {
  it("returns the same buffer when rates match", () => {
    const input = new Float32Array([0.1, 0.2, 0.3]);
    expect(resampleFloat32(input, 16000, 16000)).toBe(input);
  });

  it("halves the length when downsampling by 2x", () => {
    const input = new Float32Array(200).fill(0.5);
    const output = resampleFloat32(input, 32000, 16000);
    expect(output.length).toBe(100);
  });

  it("doubles the length when upsampling by 2x", () => {
    const input = new Float32Array(100).fill(0.5);
    const output = resampleFloat32(input, 16000, 32000);
    expect(output.length).toBe(200);
  });

  it("interpolates between samples rather than just dropping them", () => {
    const input = new Float32Array([0, 1, 0, 1, 0, 1, 0, 1]);
    const output = resampleFloat32(input, 8, 4);
    // Downsampling 2x should land roughly at even-ish indices, staying in range.
    for (const v of output) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it("handles empty input", () => {
    expect(resampleFloat32(new Float32Array(0), 48000, 16000).length).toBe(0);
  });
});

describe("floatTo16BitPCM / pcm16ToFloat32 round trip", () => {
  it("round-trips silence exactly", () => {
    const input = new Float32Array([0, 0, 0]);
    const pcm = floatTo16BitPCM(input);
    const output = pcm16ToFloat32(pcm);
    expect(Array.from(output)).toEqual([0, 0, 0]);
  });

  it("round-trips full-scale positive and negative samples within rounding error", () => {
    const input = new Float32Array([1, -1, 0.5, -0.5]);
    const output = pcm16ToFloat32(floatTo16BitPCM(input));
    for (let i = 0; i < input.length; i++) {
      expect(output[i]).toBeCloseTo(input[i], 3);
    }
  });

  it("clamps out-of-range samples instead of wrapping", () => {
    const input = new Float32Array([2, -2]);
    const output = pcm16ToFloat32(floatTo16BitPCM(input));
    expect(output[0]).toBeCloseTo(1, 3);
    expect(output[1]).toBeCloseTo(-1, 3);
  });

  it("produces 2 bytes per sample, little-endian", () => {
    const input = new Float32Array([1]); // should encode to 0x7fff
    const pcm = floatTo16BitPCM(input);
    expect(pcm.byteLength).toBe(2);
    const view = new DataView(pcm);
    expect(view.getUint8(0)).toBe(0xff);
    expect(view.getUint8(1)).toBe(0x7f);
  });
});

describe("encodeMicChunk", () => {
  it("resamples to the live input rate and returns 16-bit PCM bytes", () => {
    const input = new Float32Array(480).fill(0.25); // 10ms at 48kHz
    const pcm = encodeMicChunk(input, 48000);
    const expectedSamples = Math.round((480 * LIVE_INPUT_SAMPLE_RATE) / 48000);
    expect(pcm.byteLength).toBe(expectedSamples * 2);
  });

  it("is a no-op resample when already at the live input rate", () => {
    const input = new Float32Array([0.1, -0.1, 0.2]);
    const pcm = encodeMicChunk(input, LIVE_INPUT_SAMPLE_RATE);
    expect(pcm.byteLength).toBe(input.length * 2);
  });
});

describe("rmsAmplitude", () => {
  it("is zero for silence", () => {
    expect(rmsAmplitude(new Float32Array(100))).toBe(0);
  });

  it("is zero for an empty buffer", () => {
    expect(rmsAmplitude(new Float32Array(0))).toBe(0);
  });

  it("is 1 for a full-scale constant signal", () => {
    expect(rmsAmplitude(new Float32Array(10).fill(1))).toBeCloseTo(1, 5);
  });

  it("is higher for louder signals", () => {
    const quiet = new Float32Array(100).fill(0.1);
    const loud = new Float32Array(100).fill(0.8);
    expect(rmsAmplitude(loud)).toBeGreaterThan(rmsAmplitude(quiet));
  });
});
