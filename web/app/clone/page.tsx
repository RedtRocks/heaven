"use client";

import { useState, useEffect } from "react";
import Chat from "@/components/Chat";
import FaceStage from "@/components/FaceStage";
import { getApiUrl } from "@/lib/api";

export default function ClonePage() {
  const [playing, setPlaying] = useState<number | null>(null);

  async function playVoice(text: string, messageId: number) {
    try {
      const response = await fetch(getApiUrl("/voice/speak"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        if (response.status === 404) {
          console.log("Voice endpoint not available");
          return;
        }
        throw new Error("Failed to generate voice");
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      setPlaying(messageId);
      audio.onended = () => setPlaying(null);
      audio.play();
    } catch (err) {
      console.error("Failed to play voice:", err);
    }
  }

  // Override Chat component to add voice button
  return (
    <div className="flex flex-col h-screen bg-white dark:bg-slate-900">
      <div className="flex-1 overflow-y-auto p-4 space-y-4 flex flex-col">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
            Chat with your Clone
          </h2>
          <FaceStage />
        </div>
        <div className="flex-1 min-h-0">
          <Chat endpoint="/clone/chat" useFallback={true} />
        </div>
      </div>
    </div>
  );
}
