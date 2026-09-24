"use client";

import { useState, useRef } from "react";

interface AudioRecorderProps {
  onAudioRecorded: (blob: Blob) => void;
}

export default function AudioRecorder({ onAudioRecorded }: AudioRecorderProps) {
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/wav",
        });
        onAudioRecorded(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setRecording(true);
    } catch (err) {
      console.error("Failed to access microphone:", err);
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
    }
  }

  return (
    <button
      type="button"
      onClick={recording ? stopRecording : startRecording}
      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
        recording
          ? "bg-red-600 text-white hover:bg-red-700"
          : "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white hover:bg-slate-300 dark:hover:bg-slate-600"
      }`}
    >
      {recording ? (
        <>
          <span className="inline-block w-2 h-2 bg-red-400 rounded-full animate-pulse mr-2"></span>
          Stop Recording
        </>
      ) : (
        <>🎤 Record Audio</>
      )}
    </button>
  );
}
