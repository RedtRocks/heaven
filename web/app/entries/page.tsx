"use client";

import { useState } from "react";
import AudioRecorder from "@/components/AudioRecorder";
import { post, getApiUrl } from "@/lib/api";

export default function EntriesPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [recordingLoading, setRecordingLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || loading) return;

    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      await post("/entries", { text });
      setText("");
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save entry");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleAudioRecorded(audioBlob: Blob) {
    setRecordingLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.wav");

      const response = await fetch(getApiUrl("/entries/audio"), {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload audio");
    } finally {
      setRecordingLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 p-4">
      <div className="max-w-2xl mx-auto py-8">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
          Today's Entry
        </h1>
        <p className="text-slate-600 dark:text-slate-400 mb-8">
          Write or record what happened today
        </p>

        {success && (
          <div className="mb-4 p-4 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 rounded-lg">
            ✓ Entry saved successfully
          </div>
        )}

        {error && (
          <div className="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 rounded-lg">
            Error: {error}
          </div>
        )}

        <div className="space-y-6">
          {/* Text Entry */}
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Written Entry
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="What happened today? What did you feel? What did you learn?"
                className="w-full h-64 p-4 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !text.trim()}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {loading ? "Saving..." : "Save Entry"}
              </button>
            </form>
          </div>

          {/* Voice Entry */}
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Voice Entry
            </h2>
            <div className="space-y-4">
              <p className="text-slate-600 dark:text-slate-400">
                Record your voice instead of typing
              </p>
              <AudioRecorder
                onAudioRecorded={handleAudioRecorded}
              />
              {recordingLoading && (
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  Uploading...
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
