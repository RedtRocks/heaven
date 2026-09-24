"use client";

import { useState, useEffect } from "react";
import AudioRecorder from "@/components/AudioRecorder";
import { get, post, getApiUrl } from "@/lib/api";

interface SeedQuestion {
  question_id: string;
  text: string;
  category: string;
}

interface Trait {
  id: number;
  text: string;
  source: string;
  confirmed: boolean;
}

interface SeedAnswerOut {
  question_id: string;
  traits: Trait[];
}

export default function SeedPage() {
  const [question, setQuestion] = useState<SeedQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traits, setTraits] = useState<Trait[]>([]);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    loadNextQuestion();
  }, []);

  async function loadNextQuestion() {
    setLoading(true);
    setError(null);
    setAnswer("");
    setTraits([]);
    try {
      const data = await get<SeedQuestion | null>("/seed/next");
      if (data === null) {
        setCompleted(true);
        setQuestion(null);
      } else {
        setQuestion(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load question");
    } finally {
      setLoading(false);
    }
  }

  async function submitAnswer(text: string) {
    if (!question || !text.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      const response = await post<SeedAnswerOut>("/seed/answer", {
        question_id: question.question_id,
        text,
      });
      setTraits(response.traits || []);
      setAnswer("");
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await loadNextQuestion();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit answer");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAudioRecorded(audioBlob: Blob) {
    if (!question) return;

    setSubmitting(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("question_id", question.question_id);
      formData.append("audio", audioBlob, "answer.wav");

      const response = await fetch(getApiUrl("/seed/answer/audio"), {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }

      const data = await response.json();
      setTraits(data.traits || []);
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await loadNextQuestion();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload audio");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 flex items-center justify-center">
        <div className="text-slate-600 dark:text-slate-400">Loading...</div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 flex items-center justify-center p-4">
        <div className="max-w-md text-center">
          <div className="text-6xl mb-4">✓</div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
            Interview Complete
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mb-8">
            Thank you for sharing. Your traits have been inferred and are ready for review.
          </p>
          <a
            href="/traits"
            className="inline-block px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Review Traits
          </a>
        </div>
      </div>
    );
  }

  if (!question) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 flex items-center justify-center">
        <div className="text-slate-600 dark:text-slate-400">No questions available</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 p-4">
      <div className="max-w-2xl mx-auto py-8">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-8">
          Seed Interview
        </h1>

        {error && (
          <div className="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 rounded-lg">
            Error: {error}
          </div>
        )}

        <div className="bg-white dark:bg-slate-800 rounded-lg p-8 shadow-sm">
          <div className="mb-6">
            <span className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase">
              {question.category}
            </span>
            <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
              {question.text}
            </p>
          </div>

          {traits.length > 0 && (
            <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900 rounded-lg">
              <p className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-3">
                Inferred Traits:
              </p>
              <ul className="space-y-2">
                {traits.map((trait) => (
                  <li
                    key={trait.id}
                    className="text-sm text-blue-800 dark:text-blue-200"
                  >
                    • {trait.text}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Your Answer
              </label>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your response..."
                className="w-full p-4 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-500 dark:placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 h-32"
                disabled={submitting}
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => submitAnswer(answer)}
                disabled={submitting || !answer.trim()}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {submitting ? "Submitting..." : "Submit"}
              </button>
              <AudioRecorder
                onAudioRecorded={handleAudioRecorded}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
