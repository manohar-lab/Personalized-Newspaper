"use client";

import React, { useState, useEffect } from "react";
import { fetchWhyAmISeeingThis, muteTopic, seeLessEntity, muteSource } from "@/lib/api";

interface WhyThisStoryModalProps {
  articleId: string;
  isOpen: boolean;
  onClose: () => void;
  token: string;
}

export default function WhyThisStoryModal({
  articleId,
  isOpen,
  onClose,
  token,
}: WhyThisStoryModalProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !articleId) return;
    setLoading(true);
    setFeedbackSuccess(null);
    fetchWhyAmISeeingThis(articleId, token)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, [isOpen, articleId, token]);

  if (!isOpen) return null;

  const handleMute = async () => {
    if (!data?.topic_id) return;
    try {
      await muteTopic(data.topic_id, token);
      setFeedbackSuccess(`Muted topic '${data.topic_name || "this topic"}'`);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl animate-fadeIn text-slate-100">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-indigo-400 text-lg">💡</span>
            <h3 className="font-bold text-white text-base">Why am I seeing this?</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg transition"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="py-8 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400 font-medium">Analyzing recommendation reasons...</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Story</p>
              <h4 className="text-sm font-semibold text-white mt-0.5 line-clamp-2">{data?.title}</h4>
            </div>

            {/* Reasons List */}
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2.5">
              <p className="text-xs font-bold text-indigo-300 uppercase tracking-wider">Curation Factors</p>
              <ul className="space-y-2">
                {data?.reasons?.map((reason: string, idx: number) => (
                  <li key={idx} className="text-xs text-slate-200 flex items-start gap-2 leading-relaxed">
                    <span className="text-indigo-400 font-bold">•</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Feedback notification */}
            {feedbackSuccess && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs rounded-xl font-medium">
                ✓ {feedbackSuccess}
              </div>
            )}

            {/* One-click user corrections */}
            <div className="pt-2 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-slate-400">Not relevant?</span>
              <div className="flex items-center gap-2">
                {data?.topic_id && (
                  <button
                    onClick={handleMute}
                    className="px-3 py-1.5 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs font-medium rounded-lg border border-rose-500/20 transition"
                  >
                    🚫 Mute {data.topic_name || "Topic"}
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
