"use client";

import React, { useEffect, useState } from "react";
import { UserInterest, Topic } from "@/types";
import { fetchMyInterests, fetchTopics, addOrUpdateInterest, removeInterest } from "@/lib/api";
import { X, Trash2, Plus, RefreshCw, AlertCircle, Check } from "lucide-react";

interface MyInterestsModalProps {
  isOpen: boolean;
  onClose: () => void;
  token: string;
}

export const MyInterestsModal: React.FC<MyInterestsModalProps> = ({
  isOpen,
  onClose,
  token,
}) => {
  const [interests, setInterests] = useState<UserInterest[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Interest form state
  const [selectedTopicSlug, setSelectedTopicSlug] = useState("");
  const [score, setScore] = useState(0.85);
  const [prefType, setPrefType] = useState<"POSITIVE" | "NEGATIVE">("POSITIVE");
  const [adding, setAdding] = useState(false);

  const loadInterests = async () => {
    try {
      setLoading(true);
      setError(null);
      const [fetchedInterests, fetchedTopics] = await Promise.all([
        fetchMyInterests(token),
        fetchTopics(),
      ]);
      setInterests(fetchedInterests);
      setTopics(fetchedTopics);

      if (fetchedTopics.length > 0) {
        setSelectedTopicSlug(fetchedTopics[0].slug);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load preferences.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadInterests();
    }
  }, [isOpen, token]);

  if (!isOpen) return null;

  const handleAddOrUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTopicSlug) return;
    try {
      setAdding(true);
      setError(null);
      await addOrUpdateInterest(token, selectedTopicSlug, score, prefType);
      await loadInterests();
    } catch (err: any) {
      setError(err.message || "Failed to add/update interest.");
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (topicSlug: string) => {
    try {
      setError(null);
      await removeInterest(token, topicSlug);
      setInterests(interests.filter((i) => i.topic_slug !== topicSlug));
    } catch (err: any) {
      setError(err.message || "Failed to remove interest.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl bg-[#FAF9F5] border-2 border-[#121212] shadow-[8px_8px_0px_0px_rgba(18,18,18,1)] p-6 font-serif max-h-[90vh] flex flex-col">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#121212] hover:opacity-75 transition-opacity"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center pb-4 border-b border-[#D3CBB9] mb-4 shrink-0">
          <span className="text-xs font-sans tracking-widest uppercase text-[#8C8275]">
            PostgreSQL Database State
          </span>
          <h2 className="text-2xl font-bold uppercase tracking-tight text-[#121212] mt-1">
            My Topic Preferences
          </h2>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-300 text-red-800 text-sm font-sans flex items-center gap-2 shrink-0">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Add/Edit Form */}
        <form
          onSubmit={handleAddOrUpdate}
          className="mb-6 p-4 bg-[#F3EFE6] border border-[#D3CBB9] font-sans shrink-0 space-y-3"
        >
          <span className="text-xs font-bold uppercase text-[#121212] block">
            Add or Modify Topic Preference
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end text-xs">
            <div className="sm:col-span-2">
              <label className="block font-semibold mb-1 text-[#4A453E]">Topic</label>
              <select
                value={selectedTopicSlug}
                onChange={(e) => setSelectedTopicSlug(e.target.value)}
                className="w-full p-2 bg-white border border-[#D3CBB9] focus:outline-none"
              >
                {topics.map((t) => (
                  <option key={t.id} value={t.slug}>
                    {t.name} ({t.slug})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-semibold mb-1 text-[#4A453E]">
                Preference Type
              </label>
              <select
                value={prefType}
                onChange={(e) => setPrefType(e.target.value as any)}
                className="w-full p-2 bg-white border border-[#D3CBB9] focus:outline-none"
              >
                <option value="POSITIVE">POSITIVE</option>
                <option value="NEGATIVE">NEGATIVE</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold mb-1 text-[#4A453E]">
                Score (0.0 - 1.0)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.0"
                max="1.0"
                value={score}
                onChange={(e) => setScore(parseFloat(e.target.value))}
                className="w-full p-2 bg-white border border-[#D3CBB9] focus:outline-none"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={adding}
            className="px-4 py-2 bg-[#121212] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#2A2A2A] transition-colors flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{adding ? "Saving..." : "Save Preference"}</span>
          </button>
        </form>

        {/* List of Stored Preferences */}
        <div className="overflow-y-auto flex-1 pr-1 font-sans">
          {loading ? (
            <p className="text-center text-sm text-[#8C8275] py-8 font-serif">
              Loading preferences...
            </p>
          ) : interests.length === 0 ? (
            <p className="text-center text-sm text-[#8C8275] py-8 font-serif italic">
              No preferences stored in PostgreSQL database yet. Complete onboarding above!
            </p>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b-2 border-[#121212] uppercase font-bold text-[#121212]">
                  <th className="py-2 px-2">Topic</th>
                  <th className="py-2 px-2">Type</th>
                  <th className="py-2 px-2">Score</th>
                  <th className="py-2 px-2">Source</th>
                  <th className="py-2 px-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#D3CBB9]">
                {interests.map((item) => (
                  <tr key={item.id} className="hover:bg-[#F3EFE6]/50 transition-colors">
                    <td className="py-2.5 px-2 font-semibold text-[#121212]">
                      {item.topic_name}
                      <span className="block text-[10px] font-mono text-[#8C8275]">
                        {item.topic_slug}
                      </span>
                    </td>
                    <td className="py-2.5 px-2">
                      <span
                        className={`inline-block px-2 py-0.5 text-[10px] font-bold rounded uppercase ${
                          item.preference_type === "POSITIVE"
                            ? "bg-emerald-100 text-emerald-900 border border-emerald-300"
                            : "bg-rose-100 text-rose-900 border border-rose-300"
                        }`}
                      >
                        {item.preference_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 font-mono font-bold">
                      {item.interest_score.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-2 font-mono text-[10px] text-[#4A453E]">
                      {item.source}
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      <button
                        onClick={() => handleRemove(item.topic_slug)}
                        className="text-rose-700 hover:text-rose-900 p-1 transition-colors"
                        title="Delete preference"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
