"use client";

import { useState, useEffect } from "react";
import { get } from "@/lib/api";

interface DigestItem {
  memory_id: number;
  text: string;
  proposed_visibility: string;
  release_at: string;
}

interface DigestResponse {
  items: DigestItem[];
  text: string;
}

export default function DigestPage() {
  const [digest, setDigest] = useState<DigestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDigest();
  }, []);

  async function loadDigest() {
    setLoading(true);
    setError(null);
    try {
      const data = await get<DigestResponse>("/digest");
      setDigest(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load digest");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 flex items-center justify-center">
        <div className="text-slate-600 dark:text-slate-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800 p-4">
      <div className="max-w-2xl mx-auto py-8">
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
          Release Digest
        </h1>
        <p className="text-slate-600 dark:text-slate-400 mb-8">
          Memories coming up for release to your Clone
        </p>

        {error && (
          <div className="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 rounded-lg">
            Error: {error}
          </div>
        )}

        {digest && digest.items.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-600 dark:text-slate-400">
              No memories pending release.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {digest && digest.text && (
              <div className="bg-blue-50 dark:bg-blue-900 rounded-lg p-6 border border-blue-200 dark:border-blue-800">
                <h2 className="text-lg font-semibold text-blue-900 dark:text-blue-100 mb-4">
                  Summary
                </h2>
                <p className="text-blue-800 dark:text-blue-200 whitespace-pre-wrap">
                  {digest.text}
                </p>
              </div>
            )}

            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                Memories ({digest?.items.length || 0})
              </h2>
              {digest?.items.map((item) => (
                <div
                  key={item.memory_id}
                  className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm border border-slate-200 dark:border-slate-700"
                >
                  <div className="mb-3">
                    <p className="text-slate-900 dark:text-white break-words">
                      {item.text}
                    </p>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded">
                      Visibility: {item.proposed_visibility}
                    </span>
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded">
                      Releases: {new Date(item.release_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
