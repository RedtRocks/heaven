"use client";

import Chat from "@/components/Chat";
import FaceStage from "@/components/FaceStage";

export default function ClonePage() {
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
          <Chat endpoint="/clone/chat" enableVideo={true} />
        </div>
      </div>
    </div>
  );
}
