"use client";

import { useRef } from "react";
import Chat from "@/components/Chat";
import FaceStage from "@/components/FaceStage";
import type { FaceStageHandle } from "@/components/FaceStageCanvas";

export default function ClonePage() {
  const faceRef = useRef<FaceStageHandle>(null);

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-slate-900">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white p-4 pb-0">
        Chat with your Clone
      </h2>
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-4 p-4">
        <div className="lg:w-[420px] lg:flex-shrink-0">
          <FaceStage ref={faceRef} />
        </div>
        <div className="flex-1 min-h-0">
          <Chat
            endpoint="/clone/chat"
            enableVideo={true}
            onAssistantReply={(text) => faceRef.current?.speak(text)}
          />
        </div>
      </div>
    </div>
  );
}
