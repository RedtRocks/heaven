"use client";

import { useState, useEffect } from "react";
import { get, patch } from "@/lib/api";

interface Memory {
  id: number;
  text: string;
  happened_on: string | null;
  sealed: boolean;
  sensitive_category: string | null;
  proposed_visibility: string;
  visibility_person_ids: number[];
  about_person_id: number | null;
  said_to_their_face: boolean | null;
  release_at: string;
  owner_reviewed: boolean;
  created_at: string;
  participant_ids: number[];
}

export default function MemoriesPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMemories();
  }, []);

  async function loadMemories() {
    setLoading(true);
    setError(null);
    try {
      const data = await get<Memory[]>("/memories");
      setMemories(data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load memories");
    } finally {
      setLoading(false);
    }
  }

  async function toggleSeal(id: number, sealed: boolean) {
    try {
      const updatedMemory = await patch<Memory>(`/memories/${id}`, { sealed: !sealed });
      setMemories(
        memories.map((m) => (m.id === id ? updatedMemory : m))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update memory");
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
          Memories
        </h1>
        <p className="text-slate-600 dark:text-slate-400 mb-8">
          Your archive of memories, sealed and unsealed
        </p>

        {error && (
          <div className="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 rounded-lg">
            Error: {error}
          </div>
        )}

        {memories.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-600 dark:text-slate-400">
              No memories yet. Start by writing an entry.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {memories.map((memory) => (
              <div
                key={memory.id}
                className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm border border-slate-200 dark:border-slate-700"
              >
                <div className="space-y-3">
                  <div>
                    <p className="text-slate-900 dark:text-white mb-2 break-words">
                      {memory.text}
                    </p>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    {memory.happened_on && (
                      <span className="text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded">
                        {new Date(memory.happened_on).toLocaleDateString()}
                      </span>
                    )}
                    {memory.sensitive_category && (
                      <span className="text-xs font-medium text-orange-600 dark:text-orange-400 bg-orange-100 dark:bg-orange-900 px-2 py-1 rounded">
                        {memory.sensitive_category}
                      </span>
                    )}
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded">
                      Visibility: {memory.proposed_visibility}
                    </span>
                  </div>

                  <button
                    onClick={() => toggleSeal(memory.id, memory.sealed)}
                    className={`px-3 py-1 rounded-lg font-medium whitespace-nowrap transition-colors ${
                      memory.sealed
                        ? "bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-100 hover:bg-red-200 dark:hover:bg-red-800"
                        : "bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-100 hover:bg-blue-200 dark:hover:bg-blue-800"
                    }`}
                  >
                    {memory.sealed ? "🔒 Sealed" : "🔓 Unseal"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
