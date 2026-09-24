"use client";

import { useState, useEffect } from "react";
import { get, patch } from "@/lib/api";

interface Trait {
  id: number;
  text: string;
  source: string;
  confirmed: boolean;
  about_person_id?: number | null;
  said_to_their_face: boolean;
}

export default function TraitsPage() {
  const [traits, setTraits] = useState<Trait[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadTraits = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await get<Trait[]>("/traits");
        setTraits(data || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load traits");
      } finally {
        setLoading(false);
      }
    };
    loadTraits();
  }, []);

  async function toggleConfirmed(trait: Trait) {
    try {
      await patch(`/traits/${trait.id}`, { confirmed: !trait.confirmed });
      setTraits(
        traits.map((t) =>
          t.id === trait.id ? { ...t, confirmed: !trait.confirmed } : t
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update trait");
    }
  }

  async function toggleSaidToTheirFace(trait: Trait) {
    try {
      await patch(`/traits/${trait.id}`, {
        said_to_their_face: !trait.said_to_their_face,
      });
      setTraits(
        traits.map((t) =>
          t.id === trait.id
            ? { ...t, said_to_their_face: !trait.said_to_their_face }
            : t
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update trait");
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
          Traits
        </h1>
        <p className="text-slate-600 dark:text-slate-400 mb-8">
          Review inferred traits about yourself. Confirm the ones that ring true.
        </p>

        {error && (
          <div className="mb-4 p-4 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 rounded-lg">
            Error: {error}
          </div>
        )}

        {traits.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-600 dark:text-slate-400">
              No traits yet. Answer seed questions or entries to infer traits.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {traits.map((trait) => (
              <div
                key={trait.id}
                className="bg-white dark:bg-slate-800 rounded-lg p-6 shadow-sm border border-slate-200 dark:border-slate-700"
              >
                <div className="mb-4">
                  <p className="text-slate-900 dark:text-white font-medium mb-2">
                    {trait.text}
                  </p>
                  <div className="flex gap-2 flex-wrap">
                    <span className="text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded">
                      {trait.source}
                    </span>
                    {trait.about_person_id && (
                      <span className="text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-1 rounded">
                        About someone else
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex gap-3 flex-wrap">
                  <button
                    onClick={() => toggleConfirmed(trait)}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      trait.confirmed
                        ? "bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-100 hover:bg-green-200 dark:hover:bg-green-800"
                        : "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600"
                    }`}
                  >
                    {trait.confirmed ? "✓ Confirmed" : "Confirm"}
                  </button>

                  {!trait.about_person_id && (
                    <button
                      onClick={() => toggleSaidToTheirFace(trait)}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        trait.said_to_their_face
                          ? "bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-100 hover:bg-purple-200 dark:hover:bg-purple-800"
                          : "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600"
                      }`}
                    >
                      {trait.said_to_their_face
                        ? "💬 Said to face"
                        : "Said to face?"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
