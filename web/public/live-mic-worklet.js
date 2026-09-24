// AudioWorkletProcessor for live mode: runs on the audio rendering thread, so it can't
// do the PCM encoding itself (no access to lib/liveAudio's TS module there). It just
// forwards raw Float32 mic samples to the main thread, where LiveTalk.tsx resamples and
// encodes them (see lib/liveAudio.ts) before sending over the WebSocket.
class LiveMicProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0] && input[0].length > 0) {
      // Copy out of the reused input buffer before posting.
      const chunk = new Float32Array(input[0]);
      this.port.postMessage(chunk, [chunk.buffer]);
    }
    return true;
  }
}

registerProcessor("live-mic-processor", LiveMicProcessor);
