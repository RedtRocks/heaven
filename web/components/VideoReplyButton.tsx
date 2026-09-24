"use client";

import { useState } from "react";
import { getApiUrl } from "@/lib/api";

interface VideoReplyButtonProps {
  text: string;
  onVideoReady?: (videoUrl: string) => void;
}

interface FaceJobOut {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  mp4_url?: string;
  error?: string;
}

export default function VideoReplyButton({
  text,
  onVideoReady,
}: VideoReplyButtonProps) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerateVideo() {
    setGenerating(true);
    setError(null);

    try {
      // Create the face job
      const formData = new FormData();
      formData.append("text", text);

      const response = await fetch(getApiUrl("/face/jobs"), {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Failed to create face job: ${response.status}`);
      }

      const job = (await response.json()) as FaceJobOut;

      // Poll for completion
      let currentJob = job;
      const maxAttempts = 120; // 10 minutes with 5s polling
      let attempts = 0;

      while (
        currentJob.status !== "done" &&
        currentJob.status !== "error" &&
        attempts < maxAttempts
      ) {
        await new Promise((resolve) => setTimeout(resolve, 5000));

        const statusResponse = await fetch(
          getApiUrl(`/face/jobs/${job.job_id}`)
        );
        if (!statusResponse.ok) {
          throw new Error("Failed to get job status");
        }

        currentJob = (await statusResponse.json()) as FaceJobOut;
        attempts++;
      }

      if (currentJob.status === "error") {
        setError(currentJob.error || "Video generation failed");
      } else if (currentJob.status === "done" && currentJob.mp4_url) {
        onVideoReady?.(currentJob.mp4_url);
      } else {
        setError("Video generation timed out");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate video");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handleGenerateVideo}
        disabled={generating}
        className="px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {generating ? "Generating video..." : "🎬 Generate video"}
      </button>
      {error && (
        <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}
