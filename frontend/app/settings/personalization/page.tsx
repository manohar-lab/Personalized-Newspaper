"use client";

import React, { useState, useEffect } from "react";
import {
  fetchPersonalizationProfile,
  updatePersonalizationSettings,
  addExplicitInterest,
  deleteExplicitInterest,
  searchTopicsHierarchy,
  followTopic,
  muteTopic,
  unmuteTopic,
  adjustTopicFeedback,
  followEntity,
  muteEntity,
  seeLessEntity,
  preferSource,
  muteSource,
  reduceSource,
  pausePersonalizationLearning,
  resumePersonalizationLearning,
  resetPersonalizationProfile,
  rebuildPersonalizationProfile,
  clearTemporaryInterests,
} from "@/lib/api";

export default function PersonalizationControlCenterPage() {
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("explicit");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Search topic state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  // Modal states
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") || "" : "";

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await fetchPersonalizationProfile(token);
      setProfile(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load personalization profile.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const showToast = (msg: string) => {
    setActionMessage(msg);
    setTimeout(() => setActionMessage(null), 4000);
  };

  const handleSearchTopics = async (q: string) => {
    setSearchQuery(q);
    if (!q.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      setSearching(true);
      const results = await searchTopicsHierarchy(q, token);
      setSearchResults(results);
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  // --- Quick Actions ---
  const handleToggleLearning = async () => {
    if (!profile) return;
    try {
      if (profile.settings.learning_enabled) {
        await pausePersonalizationLearning(token);
        showToast("Personalization learning paused.");
      } else {
        await resumePersonalizationLearning(token);
        showToast("Personalization learning resumed.");
      }
      await loadProfile();
    } catch (err: any) {
      alert(err.message || "Failed to toggle learning.");
    }
  };

  const handleClearTemporary = async () => {
    try {
      await clearTemporaryInterests(token);
      showToast("Temporary and trending interests cleared.");
      await loadProfile();
    } catch (err: any) {
      alert(err.message || "Failed to clear temporary interests.");
    }
  };

  const handleRebuild = async () => {
    try {
      setRebuilding(true);
      const res = await rebuildPersonalizationProfile(token);
      showToast(`Profile rebuilt! ${res.evidence_events_processed} events processed in ${res.duration_ms}ms.`);
      await loadProfile();
    } catch (err: any) {
      alert(err.message || "Rebuild failed.");
    } finally {
      setRebuilding(false);
    }
  };

  const handleReset = async () => {
    try {
      setResetting(true);
      await resetPersonalizationProfile(token);
      showToast("Personalization profile reset to fresh state.");
      setShowResetModal(false);
      await loadProfile();
    } catch (err: any) {
      alert(err.message || "Reset failed.");
    } finally {
      setResetting(false);
    }
  };

  // --- Settings Update ---
  const handleUpdateSetting = async (key: string, value: any) => {
    try {
      await updatePersonalizationSettings({ [key]: value }, token);
      showToast(`Updated ${key.replace("_", " ")} to ${value}`);
      await loadProfile();
    } catch (err: any) {
      alert(err.message || "Failed to update setting.");
    }
  };

  const handleUpdateSection = async (sectionKey: string, value: string) => {
    if (!profile) return;
    try {
      const updated = { ...profile.settings.section_preferences, [sectionKey]: value };
      await updatePersonalizationSettings({ section_preferences: updated }, token);
      showToast(`Section ${sectionKey} set to ${value}`);
      await loadProfile();
    } catch (err: any) {
      alert(err.message || "Failed to update section.");
    }
  };

  // --- Topic Actions ---
  const handleFollowTopic = async (topicId: string, name: string) => {
    try {
      await followTopic(topicId, token);
      showToast(`Following topic: ${name}`);
      setSearchQuery("");
      setSearchResults([]);
      await loadProfile();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleMuteTopic = async (topicId: string, name: string) => {
    try {
      await muteTopic(topicId, token);
      showToast(`Muted topic: ${name}`);
      await loadProfile();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleUnmuteTopic = async (topicId: string, name: string) => {
    try {
      await unmuteTopic(topicId, token);
      showToast(`Unmuted topic: ${name}`);
      await loadProfile();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleAdjustTopic = async (topicId: string, action: string) => {
    try {
      await adjustTopicFeedback(topicId, action, token);
      showToast(`Preference adjusted: ${action}`);
      await loadProfile();
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading && !profile) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400 font-medium">Loading Personalization Control Center...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="border-b border-slate-800 pb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-2 border border-indigo-500/20">
              🧠 Control Center
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              Personalization Transparency & Controls
            </h1>
            <p className="mt-2 text-sm text-slate-400 max-w-2xl">
              AI learns automatically from how you read, but you remain in complete control. Understand why news appears and calibrate your edition.
            </p>
          </div>

          {/* Global Quick Action Toggles */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleToggleLearning}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition border ${
                profile?.settings?.learning_enabled
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20"
              }`}
            >
              {profile?.settings?.learning_enabled ? "⏸️ Pause Learning" : "▶️ Resume Learning"}
            </button>
            <button
              onClick={handleRebuild}
              disabled={rebuilding}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition disabled:opacity-50"
            >
              {rebuilding ? "Rebuilding..." : "🔄 Rebuild Profile"}
            </button>
            <button
              onClick={() => setShowResetModal(true)}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 transition"
            >
              ⚠️ Reset
            </button>
          </div>
        </div>

        {/* Action Message Toast */}
        {actionMessage && (
          <div className="p-4 rounded-xl bg-indigo-900/40 border border-indigo-500/40 text-indigo-200 text-sm font-medium flex items-center justify-between animate-fadeIn">
            <span>✨ {actionMessage}</span>
            <button onClick={() => setActionMessage(null)} className="text-indigo-400 hover:text-white">✕</button>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex overflow-x-auto space-x-2 border-b border-slate-800 pb-2 scrollbar-none">
          {[
            { id: "explicit", label: "🎯 Your Interests", count: profile?.explicit_interests?.length },
            { id: "inferred", label: "🤖 AI Learned Topics", count: profile?.inferred_interests?.length },
            { id: "topics", label: "📚 Following & Muted", count: (profile?.following_topics?.length || 0) + (profile?.muted_topics?.length || 0) },
            { id: "entities", label: "🏷️ Key Entities", count: profile?.entities?.length },
            { id: "sources", label: "📰 Sources", count: profile?.sources?.length },
            { id: "discovery", label: "🧭 Discovery & Tuning" },
            { id: "trending", label: "⚡ Trending For You", count: profile?.temporary_interests?.length },
            { id: "sections", label: "📑 Sections" },
            { id: "privacy", label: "🔒 Privacy & Transparency" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap transition flex items-center gap-2 ${
                activeTab === tab.id
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  activeTab === tab.id ? "bg-white/20 text-white" : "bg-slate-800 text-slate-400"
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* TAB 1: Explicit Interests */}
        {activeTab === "explicit" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-2">Directly Chosen Interests</h2>
              <p className="text-sm text-slate-400 mb-6">
                These are explicit interests you selected. They take primary precedence in your daily newspaper curation.
              </p>

              {/* Add Interest Search */}
              <div className="relative mb-6">
                <input
                  type="text"
                  placeholder="Search and add a topic (e.g. Artificial Intelligence, Climate, Biotech)..."
                  value={searchQuery}
                  onChange={(e) => handleSearchTopics(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                />
                {searchResults.length > 0 && (
                  <div className="absolute top-full mt-2 left-0 right-0 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-30 max-h-60 overflow-y-auto">
                    {searchResults.map((t) => (
                      <div
                        key={t.id}
                        className="px-4 py-3 flex items-center justify-between hover:bg-slate-800/80 cursor-pointer border-b border-slate-800 last:border-0"
                      >
                        <div>
                          <p className="text-sm font-semibold text-white">{t.name}</p>
                          {t.parent_name && <p className="text-xs text-slate-400">Parent: {t.parent_name}</p>}
                        </div>
                        <button
                          onClick={() => handleFollowTopic(t.id, t.name)}
                          className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg"
                        >
                          + Add
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Current Explicit List */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {profile?.explicit_interests?.map((item: any) => (
                  <div
                    key={item.id}
                    className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl flex items-center justify-between group hover:border-slate-700 transition"
                  >
                    <div>
                      <p className="font-semibold text-white text-sm">{item.topic_name}</p>
                      <span className="text-xs text-emerald-400 font-medium">Explicit Preference</span>
                    </div>
                    <button
                      onClick={async () => {
                        await deleteExplicitInterest(item.id, token);
                        showToast(`Removed ${item.topic_name}`);
                        loadProfile();
                      }}
                      className="text-slate-500 hover:text-rose-400 p-1 rounded-lg transition"
                      title="Remove Interest"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: AI Learned Topics */}
        {activeTab === "inferred" && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-2">Behaviorally Learned Interests</h2>
              <p className="text-sm text-slate-400 mb-6">
                Topics inferred from reading depth, completion rates, and repeat engagement. Expand any topic to see the evidence and fine-tune AI recommendations.
              </p>

              <div className="space-y-4">
                {profile?.inferred_interests?.length === 0 ? (
                  <p className="text-slate-500 text-sm italic">No behavioral interests learned yet. Read articles to build your profile.</p>
                ) : (
                  profile?.inferred_interests?.map((topic: any) => (
                    <div
                      key={topic.topic_id}
                      className="p-5 bg-slate-950 border border-slate-800 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-3">
                          <h3 className="font-bold text-white text-base">{topic.topic_name}</h3>
                          <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                            topic.tier === "Strong interest"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : topic.tier === "Growing interest"
                              ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
                              : "bg-slate-800 text-slate-400"
                          }`}>
                            {topic.tier}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400">{topic.why_reason}</p>
                      </div>

                      {/* Controls */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          onClick={() => handleAdjustTopic(topic.topic_id, "MORE")}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
                        >
                          👍 More like this
                        </button>
                        <button
                          onClick={() => handleAdjustTopic(topic.topic_id, "LESS")}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
                        >
                          👎 Less like this
                        </button>
                        <button
                          onClick={() => handleMuteTopic(topic.topic_id, topic.topic_name)}
                          className="px-3 py-1.5 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs font-medium rounded-lg transition border border-rose-500/20"
                        >
                          🚫 Not interested
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: Following & Muted Topics */}
        {activeTab === "topics" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Following */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                Following ({profile?.following_topics?.length || 0})
              </h2>
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {profile?.following_topics?.map((t: any) => (
                  <div key={t.topic_id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
                    <span className="text-sm font-semibold text-white">{t.topic_name}</span>
                    <button
                      onClick={() => handleMuteTopic(t.topic_id, t.topic_name)}
                      className="text-xs text-slate-400 hover:text-rose-400 transition"
                    >
                      Mute
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Muted */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                Muted ({profile?.muted_topics?.length || 0})
              </h2>
              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {profile?.muted_topics?.map((t: any) => (
                  <div key={t.topic_id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-400 line-through">{t.topic_name}</span>
                    <button
                      onClick={() => handleUnmuteTopic(t.topic_id, t.topic_name)}
                      className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition"
                    >
                      Unmute
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: Key Entities */}
        {activeTab === "entities" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
            <h2 className="text-lg font-bold text-white mb-2">Key Entities & Figures</h2>
            <p className="text-sm text-slate-400 mb-4">
              Organizations, figures, and concepts tracked in your reading sessions.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {profile?.entities?.map((ent: any) => (
                <div key={ent.entity_id} className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                  <div>
                    <h3 className="font-bold text-white text-sm">{ent.name}</h3>
                    <p className="text-xs text-slate-400">{ent.why_reason}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={async () => {
                        await followEntity(ent.entity_id, token);
                        showToast(`Following ${ent.name}`);
                        loadProfile();
                      }}
                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 rounded-md"
                    >
                      Follow
                    </button>
                    <button
                      onClick={async () => {
                        await seeLessEntity(ent.entity_id, token);
                        showToast(`Reduced ${ent.name}`);
                        loadProfile();
                      }}
                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 rounded-md"
                    >
                      Less
                    </button>
                    <button
                      onClick={async () => {
                        await muteEntity(ent.entity_id, token);
                        showToast(`Muted ${ent.name}`);
                        loadProfile();
                      }}
                      className="px-2.5 py-1 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs rounded-md"
                    >
                      Mute
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 5: Sources */}
        {activeTab === "sources" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
            <h2 className="text-lg font-bold text-white mb-2">News Sources Affinity</h2>
            <p className="text-sm text-slate-400 mb-4">
              Manage preferred and muted news outlets. User source preferences are kept distinct from global source quality ratings.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {profile?.sources?.map((s: any) => (
                <div key={s.source_id} className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                  <div>
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-white text-sm">{s.name}</h3>
                      <span className="text-xs text-indigo-400">{s.affinity_label}</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{s.read_count} articles read</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={async () => {
                        await preferSource(s.source_id, token);
                        showToast(`Preferred ${s.name}`);
                        loadProfile();
                      }}
                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 rounded-md"
                    >
                      Prefer
                    </button>
                    <button
                      onClick={async () => {
                        await reduceSource(s.source_id, token);
                        showToast(`Reduced ${s.name}`);
                        loadProfile();
                      }}
                      className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 rounded-md"
                    >
                      Reduce
                    </button>
                    <button
                      onClick={async () => {
                        await muteSource(s.source_id, token);
                        showToast(`Muted ${s.name}`);
                        loadProfile();
                      }}
                      className="px-2.5 py-1 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-xs rounded-md"
                    >
                      Mute
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 6: Discovery & Tuning */}
        {activeTab === "discovery" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-8">
            <h2 className="text-lg font-bold text-white mb-2">Discovery & Curation Tuning</h2>
            
            {/* Discovery Level */}
            <div className="space-y-3 border-b border-slate-800 pb-6">
              <label className="text-sm font-bold text-white">Discovery Level</label>
              <p className="text-xs text-slate-400">
                Discovery introduces adjacent topics related to your interests so your newspaper avoids repetitive echo chambers.
              </p>
              <div className="grid grid-cols-3 gap-3">
                {["FOCUSED", "BALANCED", "EXPLORATORY"].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => handleUpdateSetting("discovery_level", lvl)}
                    className={`py-3 px-4 rounded-xl text-xs font-semibold uppercase transition border ${
                      profile?.settings?.discovery_level === lvl
                        ? "bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-600/30"
                        : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* Personalization Strength */}
            <div className="space-y-3 border-b border-slate-800 pb-6">
              <label className="text-sm font-bold text-white">Personalization Strength</label>
              <p className="text-xs text-slate-400">
                Balances your personal topic relevance against major world headlines.
              </p>
              <div className="grid grid-cols-3 gap-3">
                {["LOW", "BALANCED", "HIGH"].map((str) => (
                  <button
                    key={str}
                    onClick={() => handleUpdateSetting("personalization_strength", str)}
                    className={`py-3 px-4 rounded-xl text-xs font-semibold uppercase transition border ${
                      profile?.settings?.personalization_strength === str
                        ? "bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-600/30"
                        : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    {str}
                  </button>
                ))}
              </div>
            </div>

            {/* Topic Diversity */}
            <div className="space-y-3">
              <label className="text-sm font-bold text-white">Topic Diversity</label>
              <p className="text-xs text-slate-400">
                Controls topic variety per section to prevent single-subject dominance.
              </p>
              <div className="grid grid-cols-3 gap-3">
                {["FOCUSED", "BALANCED", "DIVERSE"].map((div) => (
                  <button
                    key={div}
                    onClick={() => handleUpdateSetting("diversity_level", div)}
                    className={`py-3 px-4 rounded-xl text-xs font-semibold uppercase transition border ${
                      profile?.settings?.diversity_level === div
                        ? "bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-600/30"
                        : "bg-slate-950 text-slate-400 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    {div}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 7: Trending For You */}
        {activeTab === "trending" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white">Temporary & Developing Affinities</h2>
                <p className="text-sm text-slate-400">
                  Short-term signals tied to breaking or rapidly updating stories. These decay automatically.
                </p>
              </div>
              <button
                onClick={handleClearTemporary}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-semibold rounded-lg transition"
              >
                Clear Recent Interests
              </button>
            </div>

            <div className="space-y-3">
              {profile?.temporary_interests?.length === 0 ? (
                <p className="text-slate-500 text-sm italic">No active short-term story signals.</p>
              ) : (
                profile?.temporary_interests?.map((item: any) => (
                  <div key={item.story_id} className="p-4 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-white text-sm">{item.title}</h3>
                      <p className="text-xs text-slate-400">{item.interaction_count} recent interactions</p>
                    </div>
                    <span className="text-xs text-indigo-400 font-medium">Temporary</span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* TAB 8: Sections */}
        {activeTab === "sections" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
            <h2 className="text-lg font-bold text-white mb-2">Newspaper Section Controls</h2>
            <p className="text-sm text-slate-400 mb-4">
              Toggle visibility for sections in your personal newspaper editions.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(profile?.settings?.section_preferences || {}).map(([secKey, secVal]: any) => (
                <div key={secKey} className="p-4 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
                  <span className="text-sm font-bold text-white">{secKey.replace("_", " ")}</span>
                  <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800">
                    {["SHOW", "REDUCE", "HIDE"].map((opt) => (
                      <button
                        key={opt}
                        onClick={() => handleUpdateSection(secKey, opt)}
                        className={`px-2.5 py-1 text-xs font-semibold rounded-md transition ${
                          secVal === opt
                            ? "bg-indigo-600 text-white"
                            : "text-slate-400 hover:text-white"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 9: Privacy & Transparency */}
        {activeTab === "privacy" && (
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
            <h2 className="text-lg font-bold text-white mb-2">Privacy & Transparent Evidence</h2>
            <p className="text-sm text-slate-400">
              The Personalized Newspaper strictly isolates behavioral profiles per user account. Your reading data is never shared.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl text-center">
                <p className="text-2xl font-black text-indigo-400">{profile?.learning_stats?.articles_read || 0}</p>
                <p className="text-xs text-slate-400 mt-1">Articles Read</p>
              </div>
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl text-center">
                <p className="text-2xl font-black text-emerald-400">{profile?.learning_stats?.topics_followed || 0}</p>
                <p className="text-xs text-slate-400 mt-1">Topics Followed</p>
              </div>
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl text-center">
                <p className="text-2xl font-black text-rose-400">{profile?.learning_stats?.topics_muted || 0}</p>
                <p className="text-xs text-slate-400 mt-1">Topics Muted</p>
              </div>
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl text-center">
                <p className="text-2xl font-black text-amber-400">{profile?.learning_stats?.inferred_interests_count || 0}</p>
                <p className="text-xs text-slate-400 mt-1">Inferred Clusters</p>
              </div>
            </div>

            <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Signals Captured</h3>
              <ul className="text-xs text-slate-300 list-disc list-inside space-y-1">
                {profile?.privacy_transparency?.data_types_used?.map((dt: string, i: number) => (
                  <li key={i}>{dt}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* RESET CONFIRMATION MODAL */}
        {showResetModal && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
              <h3 className="text-lg font-bold text-white">Reset Personalized Profile?</h3>
              <p className="text-sm text-slate-400">
                This will clear all inferred behavioral scores, keyword affinities, and temporary boosts. Your saved articles and explicit interests will remain safe.
              </p>
              <div className="flex items-center justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowResetModal(false)}
                  className="px-4 py-2 text-sm font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReset}
                  disabled={resetting}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-sm font-semibold rounded-xl transition disabled:opacity-50"
                >
                  {resetting ? "Resetting..." : "Yes, Reset Profile"}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
