import { describe, expect, it } from "vitest";
import { estimateWordTimings, isVoiceUnavailableStatus, splitSentences } from "./faceSpeech";

describe("isVoiceUnavailableStatus", () => {
  it("treats 404, 501 and 503 as 'voice not set up yet'", () => {
    expect(isVoiceUnavailableStatus(404)).toBe(true);
    expect(isVoiceUnavailableStatus(501)).toBe(true);
    expect(isVoiceUnavailableStatus(503)).toBe(true);
  });

  it("does not treat success or unrelated errors as unavailable", () => {
    expect(isVoiceUnavailableStatus(200)).toBe(false);
    expect(isVoiceUnavailableStatus(400)).toBe(false);
    expect(isVoiceUnavailableStatus(500)).toBe(false);
  });
});

describe("estimateWordTimings", () => {
  it("returns empty timings for empty text", () => {
    const result = estimateWordTimings("");
    expect(result.words).toEqual([]);
    expect(result.wtimes).toEqual([]);
    expect(result.wdurations).toEqual([]);
    expect(result.totalMs).toBe(0);
  });

  it("produces one entry per word, strictly increasing start times", () => {
    const result = estimateWordTimings("Hello there, how are you?");
    expect(result.words).toHaveLength(5);
    expect(result.wtimes).toHaveLength(5);
    expect(result.wdurations).toHaveLength(5);
    for (let i = 1; i < result.wtimes.length; i++) {
      expect(result.wtimes[i]).toBeGreaterThan(result.wtimes[i - 1]);
    }
    expect(result.totalMs).toBeGreaterThan(
      result.wtimes[result.wtimes.length - 1]
    );
  });

  it("collapses repeated whitespace and ignores empty tokens", () => {
    const result = estimateWordTimings("  a    b  ");
    expect(result.words).toEqual(["a", "b"]);
  });
});

describe("splitSentences", () => {
  it("splits on sentence-ending punctuation", () => {
    expect(
      splitSentences("Hey! It's so good to hear from you. We should still do it, you know.")
    ).toEqual(["Hey! It's so good to hear from you.", "We should still do it, you know."]);
  });

  it("keeps a trailing fragment with no final punctuation", () => {
    expect(splitSentences("I miss you. Talk soon")).toEqual(["I miss you. Talk soon"]);
  });

  it("merges very short fragments into the previous sentence", () => {
    expect(splitSentences("That was the best day of my life. Really. Truly it was.")).toEqual([
      "That was the best day of my life. Really.",
      "Truly it was.",
    ]);
  });

  it("returns nothing for blank text", () => {
    expect(splitSentences("   ")).toEqual([]);
  });
});
