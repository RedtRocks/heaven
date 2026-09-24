"use client";

import { useState } from "react";
import Chat from "@/components/Chat";
import LiveTalk, { LiveTranscriptEvent } from "@/components/LiveTalk";

/** /assistant's client-side content: the text Chat plus the "Talk live" toggle
 * (ADR 0003: Memory Assistant only, Stock Voice). Split from page.tsx so the page
 * can stay a server component and keep its `metadata` export. */
export default function AssistantLive() {
  const [liveTranscripts, setLiveTranscripts] = useState<LiveTranscriptEvent[]>([]);

  function handleTranscript(event: LiveTranscriptEvent) {
    setLiveTranscripts((prev) => {
      // Replace a trailing non-final line from the same speaker instead of piling up
      // partial transcripts as they fill in.
      if (prev.length > 0 && !prev[prev.length - 1].final && prev[prev.length - 1].speaker === event.speaker) {
        return [...prev.slice(0, -1), event];
      }
      return [...prev, event];
    });
  }

  return (
    <div className="h-screen flex flex-col">
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 px-4 py-2">
        <h1 className="text-sm font-medium text-slate-700 dark:text-slate-300">Memory Assistant</h1>
        <LiveTalk onTranscript={handleTranscript} />
      </div>
      {liveTranscripts.length > 0 && (
        <div className="border-b border-slate-200 dark:border-slate-700 px-4 py-2 max-h-32 overflow-y-auto text-sm space-y-1 bg-slate-50 dark:bg-slate-800/50">
          {liveTranscripts.map((t, i) => (
            <p
              key={i}
              className={t.speaker === "user" ? "text-slate-600 dark:text-slate-300" : "text-slate-900 dark:text-slate-100"}
            >
              <span className="font-medium">{t.speaker === "user" ? "You: " : "Assistant: "}</span>
              {t.text}
              {!t.final && <span className="opacity-50">…</span>}
            </p>
          ))}
        </div>
      )}
      <div className="flex-1 min-h-0">
        <Chat endpoint="/assistant/chat" />
      </div>
    </div>
  );
}
