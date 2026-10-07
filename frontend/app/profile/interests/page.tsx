"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  fetchUserProfileInterests,
  overrideTopicPreference,
  rebuildUserProfile,
} from "@/lib/api";
import { UserProfileInterestsResponse, TopicInterestItem } from "@/types";

export default function ProfileInterestsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfileInterestsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildMsg, setRebuildMsg] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    try {
      const data = await fetchUserProfileInterests(token);
      setProfile(data);
    } catch (err) {
      console.error("Failed to load user profile:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleOverride(topicId: string, action: string) {
    const token = localStorage.getItem("token");
    if (!token) return;

    try {
      await overrideTopicPreference(token, topicId, action);
      setActionMsg(`Preference updated successfully (${action.toLowerCase()}).`);
      setTimeout(() => setActionMsg(null), 3000);
      await loadProfile();
    } catch (err) {
      console.error("Failed to override preference:", err);
    }
  }

  async function handleRebuild() {
    const token = localStorage.getItem("token");
    if (!token) return;

    setRebuilding(true);
    setRebuildMsg(null);
    try {
      const res = await rebuildUserProfile(token);
      setRebuildMsg(
        `Rebuilt profile from ${res.evidence_events_processed} interaction signals in ${res.duration_ms}ms.`
      );
      setTimeout(() => setRebuildMsg(null), 5000);
      await loadProfile();
    } catch (err) {
      console.error("Failed to rebuild profile:", err);
      setRebuildMsg("Profile rebuild encountered an error.");
    } finally {
      setRebuilding(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#faf8f5] text-[#1c1917] p-8 flex items-center justify-center font-serif">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-stone-800 mb-4"></div>
          <p className="text-stone-600 font-sans">Analyzing your reading preferences...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#faf8f5] text-[#1c1917] font-serif p-6 md:p-12">
      <div className="max-w-4xl mx-auto">
        {/* Editorial Masthead Header */}
        <header className="border-b-2 border-stone-900 pb-6 mb-8 text-center">
          <div className="text-xs uppercase tracking-widest text-stone-500 font-sans mb-1 font-semibold">
            Personalized Newspaper Engine · Behavioral Intelligence
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-stone-900">
            YOUR READING PROFILE
          </h1>
          <p className="text-stone-600 mt-2 font-sans text-sm max-w-xl mx-auto">
            Our engine continuously learns what you actually prefer from your dwell times, completed reads, saves, and search habits—while always honoring your explicit instructions.
          </p>

          <div className="mt-4 flex flex-wrap justify-center items-center gap-3 font-sans text-xs">
            <button
              onClick={handleRebuild}
              disabled={rebuilding}
              className="px-4 py-2 bg-stone-900 text-stone-100 rounded-md font-medium hover:bg-stone-800 transition disabled:opacity-50"
            >
              {rebuilding ? "Rebuilding from Evidence..." : "↻ Rebuild Profile from History"}
            </button>
            <button
              onClick={() => router.push("/newspaper")}
              className="px-4 py-2 border border-stone-400 text-stone-800 rounded-md font-medium hover:bg-stone-200 transition"
            >
              ← Back to Broadsheet
            </button>
          </div>

          {rebuildMsg && (
            <div className="mt-3 p-2 bg-emerald-50 text-emerald-800 text-xs font-sans rounded border border-emerald-300 inline-block">
              {rebuildMsg}
            </div>
          )}
          {actionMsg && (
            <div className="mt-3 p-2 bg-blue-50 text-blue-800 text-xs font-sans rounded border border-blue-300 inline-block">
              {actionMsg}
            </div>
          )}
        </header>

        {/* Discovery & Anti-Collapse Indicators */}
        <section className="bg-stone-100 border border-stone-300 rounded-lg p-4 mb-8 font-sans text-xs text-stone-700 flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <span className="font-bold text-stone-900">Serendipity & Discovery Balance: </span>
            <span>15% of edition recommendations are preserved for adjacent topics to prevent filter bubbles.</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-stone-600">Distribution Health:</span>
            <span className="px-2 py-1 bg-stone-200 rounded font-mono font-bold text-stone-800">
              {Math.round((profile?.entropy_balance || 0.85) * 100)}% Balanced
            </span>
          </div>
        </section>

        {/* 1. Strong Interests Section */}
        <section className="mb-10">
          <div className="flex items-center justify-between border-b border-stone-300 pb-2 mb-4">
            <h2 className="text-xl font-bold uppercase tracking-wider text-stone-900">
              Strong Interests
            </h2>
            <span className="text-xs font-sans text-stone-500">
              High engagement + confirmed affinity
            </span>
          </div>

          {(!profile?.strong_interests || profile.strong_interests.length === 0) ? (
            <p className="text-stone-500 font-sans text-sm italic">
              No strong interests detected yet. Read articles or add explicit interests to build your profile.
            </p>
          ) : (
            <div className="space-y-4">
              {profile.strong_interests.map((item) => (
                <div
                  key={item.topic_id}
                  className="bg-white border border-stone-200 rounded-lg p-4 shadow-sm hover:border-stone-400 transition"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-stone-900">{item.topic_name}</span>
                        {item.explicit_override === "POSITIVE" && (
                          <span className="px-2 py-0.5 bg-amber-100 text-amber-900 text-[10px] font-sans font-bold uppercase rounded">
                            Explicit Choice
                          </span>
                        )}
                        <span className="px-2 py-0.5 bg-stone-100 text-stone-700 text-[10px] font-sans font-medium rounded">
                          {Math.round(item.confidence * 100)}% Confidence
                        </span>
                      </div>
                      <p className="text-xs text-stone-600 font-sans mt-1">
                        {item.explanation}
                      </p>
                    </div>

                    <div className="flex items-center gap-1 font-sans text-xs">
                      <button
                        onClick={() => handleOverride(item.topic_id, "SET_POSITIVE")}
                        title="Boost topic preference"
                        className="px-2 py-1 bg-stone-100 hover:bg-stone-200 rounded text-stone-700"
                      >
                        + Boost
                      </button>
                      <button
                        onClick={() => handleOverride(item.topic_id, "MUTE")}
                        title="Mute this topic"
                        className="px-2 py-1 bg-stone-100 hover:bg-rose-100 hover:text-rose-800 rounded text-stone-600"
                      >
                        Mute
                      </button>
                    </div>
                  </div>

                  {/* Affinity Bar */}
                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1 bg-stone-100 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="bg-stone-800 h-2.5 rounded-full transition-all duration-500"
                        style={{ width: `${Math.round(item.score * 100)}%` }}
                      ></div>
                    </div>
                    <span className="font-mono text-xs font-bold text-stone-800">
                      {Math.round(item.score * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 2. Growing Interests Section */}
        {profile?.growing_interests && profile.growing_interests.length > 0 && (
          <section className="mb-10">
            <div className="flex items-center justify-between border-b border-stone-300 pb-2 mb-4">
              <h2 className="text-xl font-bold uppercase tracking-wider text-stone-900">
                Growing Interests
              </h2>
              <span className="text-xs font-sans text-stone-500">
                Rising trends from recent 7-day reading activity
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {profile.growing_interests.map((item) => (
                <div
                  key={item.topic_id}
                  className="bg-white border border-stone-200 rounded-lg p-4 shadow-sm"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="font-bold text-stone-900">{item.topic_name}</span>
                      <p className="text-xs text-stone-600 font-sans mt-1">
                        {item.explanation}
                      </p>
                    </div>
                    <button
                      onClick={() => handleOverride(item.topic_id, "SET_POSITIVE")}
                      className="text-xs font-sans px-2 py-1 bg-stone-100 hover:bg-stone-200 rounded text-stone-700"
                    >
                      Follow
                    </button>
                  </div>

                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1 bg-stone-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{ width: `${Math.round(item.score * 100)}%` }}
                      ></div>
                    </div>
                    <span className="font-mono text-xs text-stone-700">
                      {Math.round(item.score * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 3. Entity & Story Affinities */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
          {/* Top Entities */}
          <section>
            <div className="border-b border-stone-300 pb-2 mb-4">
              <h2 className="text-lg font-bold uppercase tracking-wider text-stone-900">
                Key Entities & Companies
              </h2>
            </div>
            {(!profile?.entity_preferences || profile.entity_preferences.length === 0) ? (
              <p className="text-stone-500 font-sans text-xs italic">No specific entity affinities yet.</p>
            ) : (
              <div className="space-y-2">
                {profile.entity_preferences.slice(0, 6).map((ent) => (
                  <div
                    key={ent.entity_id}
                    className="bg-white border border-stone-200 rounded p-2.5 flex items-center justify-between text-xs font-sans"
                  >
                    <div>
                      <span className="font-bold text-stone-900">{ent.entity_name}</span>
                      <span className="text-[10px] text-stone-500 ml-2 uppercase">({ent.entity_type})</span>
                    </div>
                    <span className="font-mono font-bold text-stone-700">
                      {Math.round(ent.score * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Active Story Affinities */}
          <section>
            <div className="border-b border-stone-300 pb-2 mb-4">
              <h2 className="text-lg font-bold uppercase tracking-wider text-stone-900">
                Active Story Follow-Ups
              </h2>
            </div>
            {(!profile?.active_story_affinities || profile.active_story_affinities.length === 0) ? (
              <p className="text-stone-500 font-sans text-xs italic">No active story follow-ups.</p>
            ) : (
              <div className="space-y-2">
                {profile.active_story_affinities.slice(0, 4).map((st) => (
                  <div
                    key={st.story_id}
                    className="bg-white border border-stone-200 rounded p-2.5 text-xs font-sans"
                  >
                    <div className="font-bold text-stone-900 truncate">{st.story_title}</div>
                    <div className="text-[10px] text-stone-500 mt-1">
                      Temporary affinity active for multi-source updates
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* 4. Low Engagement & Muted Topics */}
        {profile?.low_engagement_topics && profile.low_engagement_topics.length > 0 && (
          <section className="mb-10 bg-stone-50 border border-stone-200 rounded-lg p-5">
            <div className="flex items-center justify-between border-b border-stone-200 pb-2 mb-3">
              <h2 className="text-base font-bold uppercase tracking-wider text-stone-700">
                Low Recent Engagement
              </h2>
              <span className="text-xs font-sans text-stone-500">
                Topics deprioritized due to skips or low dwell time
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {profile.low_engagement_topics.map((item) => (
                <div
                  key={item.topic_id}
                  className="bg-white border border-stone-300 rounded px-3 py-1.5 flex items-center gap-2 font-sans text-xs text-stone-700"
                >
                  <span>{item.topic_name}</span>
                  <button
                    onClick={() => handleOverride(item.topic_id, "SET_POSITIVE")}
                    title="Follow this topic"
                    className="text-stone-400 hover:text-stone-800 font-bold ml-1"
                  >
                    +
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
