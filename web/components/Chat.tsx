"use client";

import { useState, useRef, useEffect } from "react";
import { post } from "@/lib/api";
import VideoReplyButton from "./VideoReplyButton";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: number[];
  videoUrl?: string;
}

interface ChatResponse {
  reply: string;
  citations?: number[];
}

interface ChatProps {
  endpoint: string;
  visitorId?: number;
  enableVideo?: boolean;
}

export default function Chat({ endpoint, visitorId, enableVideo }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  function handleVideoReady(messageIdx: number, videoUrl: string) {
    setMessages((prevMessages) => {
      const updated = [...prevMessages];
      updated[messageIdx] = { ...updated[messageIdx], videoUrl };
      return updated;
    });
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input;
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const historyForApi = messages
        .filter((m) => m.role !== "assistant" || !m.citations)
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      const body: Record<string, unknown> = {
        message: userMessage,
        history: historyForApi,
      };

      if (visitorId !== undefined) {
        body.visitor_id = visitorId;
      }

      const response = await post<ChatResponse>(endpoint, body);

      const assistantMessage: Message = {
        role: "assistant",
        content: response.reply,
        citations: response.citations || [],
      };

      setMessages([
        ...messages,
        { role: "user", content: userMessage },
        assistantMessage,
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to send message"
      );
      setMessages([...messages, { role: "user", content: userMessage }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-slate-900">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-slate-500 dark:text-slate-400">
            <p className="text-center">
              Start a conversation. Be kind, be clear.
            </p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
                msg.role === "user"
                  ? "bg-slate-700 text-white dark:bg-blue-600"
                  : "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.videoUrl && (
                <div className="mt-2">
                  <video
                    src={msg.videoUrl}
                    controls
                    className="w-full rounded"
                  />
                </div>
              )}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 text-sm border-t border-opacity-30 pt-2">
                  <p className="font-semibold mb-1">Citations:</p>
                  <ul className="space-y-1">
                    {msg.citations.map((memoryId, cidx) => (
                      <li key={cidx} className="text-xs opacity-75">
                        • Memory {memoryId}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {msg.role === "assistant" && enableVideo && !msg.videoUrl && (
                <div className="mt-2">
                  <VideoReplyButton
                    text={msg.content}
                    onVideoReady={(url) => handleVideoReady(idx, url)}
                  />
                </div>
              )}
            </div>
          </div>
        ))}
        {error && (
          <div className="flex justify-center">
            <div className="bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 px-4 py-2 rounded">
              Error: {error}
            </div>
          </div>
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-100 dark:bg-slate-800 px-4 py-3 rounded-lg">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-200 dark:border-slate-700 p-4 bg-white dark:bg-slate-900"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
