"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { AuthModal } from "@/components/AuthModal";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Footer } from "@/components/Footer";
import {
  fetchCurrentUser,
  fetchDynamicInterestProfile,
  fetchTopics,
  addOrUpdateInterest,
  removeInterest,
  updateTopicPreference,
  removeLearnedInterest,
  resetLearnedProfile,
} from "@/lib/api";
import {
  User,
  Topic,
  DynamicProfileResponse,
  DynamicInterestItem,
  TopicPreferenceItem,
} from "@/types";
import {
  Sparkles,
  Sliders,
  TrendingUp,
  Flame,
  RotateCcw,
  Check,
  Trash2,
  Plus,
  Ban,
  Brain,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Info,
  CheckCircle2,
  BookOpen,
} from "lucide-react";

export default function DynamicInterestsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const [profile, setProfile] = useState<DynamicProfileResponse | null>(null);
  const [allTopics, setAllTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [showInterestsModal, setShowInterestsModal] = useState<boolean>(false);
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // New Topic Selector State
  const [selectedTopicSlug, setSelectedTopicSlug] = useState<string>("");

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token");
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser(savedToken)
        .then(setUser)
        .catch(() => {});
    } else {
      setLoading(false);
    }
  }, []);

  const loadData = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [profData, topicsData] = await Promise.all([
        fetchDynamicInterestProfile(token),
        fetchTopics(),
      ]);
      setProfile(profData);
      setAllTopics(topicsData);
    } catch (err: any) {
      console.error("Failed to load dynamic profile:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadData();
    }
  }, [token]);

  // Handlers
  const handleAddExplicitTopic = async () => {
    if (!token || !selectedTopicSlug) return;
    try {
      await addOrUpdateInterest(token, selectedTopicSlug, 0.90, "POSITIVE");
      setSelectedTopicSlug("");
      showToast("Explicit topic added to your profile");
      await loadData();
    } catch (err) {
      showToast("Failed to add topic preference");
    }
  };

  const handleRemoveExplicitTopic = async (topicSlug: string) => {
    if (!token) return;
    try {
      await removeInterest(token, topicSlug);
      showToast("Explicit interest removed");
      await loadData();
    } catch (err) {
      showToast("Failed to remove explicit interest");
    }
  };

  const handleRemoveLearnedTopic = async (topicId: string) => {
    if (!token) return;
    try {
      await removeLearnedInterest(token, topicId);
      showToast("Learned topic interest removed");
      await loadData();
    } catch (err) {
      showToast("Failed to remove learned interest");
    }
  };

  const handleSuppressTopic = async (topicId: string) => {
    if (!token) return;
    try {
      await updateTopicPreference(token, topicId, "NEGATIVE", 1.0);
      showToast("Topic marked as Not Interested & suppressed");
      await loadData();
    } catch (err) {
      showToast("Failed to update topic preference");
    }
  };

  const handleRestoreAvoidedTopic = async (topicId: string) => {
    if (!token) return;
    try {
      await updateTopicPreference(token, topicId, "NEUTRAL", 0.5);
      showToast("Topic penalty restored to neutral");
      await loadData();
    } catch (err) {
      showToast("Failed to restore topic");
    }
  };

  const handleResetLearned = async () => {
    if (!token) return;
    setIsResetting(true);
    try {
      const res = await resetLearnedProfile(token);
      setShowResetConfirm(false);
      showToast(res.message);
      await loadData();
    } catch (err) {
      showToast("Failed to reset learned interests");
    } finally {
      setIsResetting(false);
    }
  };

  // Helper to render score bar
  const renderScoreBar = (score: number) => {
    const percentage = Math.round(score * 100);
    return (
      <div className="flex items-center gap-2">
        <div className="w-24 sm:w-32 h-2 bg-[#E6DFD3] rounded-full overflow-hidden">
          <div
            className="h-full bg-[#8C2524] transition-all duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <span className="font-mono text-xs font-bold text-[#181615]">
          {percentage}%
        </span>
      </div>
    );
  };

  return (
    <div className="min-h-screen flex flex-col justify-between bg-[#FAF8F5] text-[#181615]">
      <div>
        <NewspaperHeader
          user={user}
          onOpenAuth={() => setShowAuthModal(true)}
          onOpenInterests={() => setShowInterestsModal(true)}
          onSignOut={() => {
            localStorage.removeItem("pn_auth_token");
            setToken(null);
            setUser(null);
          }}
        />

        {/* Toast */}
        {toastMessage && (
          <div className="fixed bottom-6 right-6 z-50 bg-[#181615] text-[#FAF8F5] px-5 py-3 rounded-sm shadow-xl font-sans text-xs flex items-center gap-2 border border-[#4A453E] animate-bounce">
            <Check className="w-4 h-4 text-emerald-400" />
            <span>{toastMessage}</span>
          </div>
        )}

        <main className="max-w-6xl mx-auto px-4 sm:px-8 py-10 font-sans">
          {/* Masthead Header */}
          <div className="border-b-2 border-[#181615] pb-6 mb-8 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-[#8C2524] mb-1">
                <Brain className="w-4 h-4" />
                <span>Dynamic Intelligence Engine</span>
              </div>
              <h1 className="font-editorial-heading font-black text-4xl sm:text-5xl text-[#181615] tracking-tight">
                Your Interest Profile
              </h1>
              <p className="font-editorial-body italic text-base sm:text-lg text-[#5C554E] mt-1">
                A continuously evolving intelligence profile based on your explicit preferences and deep reading behavior.
              </p>
            </div>

            {token && (
              <button
                onClick={() => setShowResetConfirm(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold uppercase tracking-wider text-[#8C2524] bg-white border border-[#DCD3C7] hover:bg-[#F3ECE2] rounded-sm transition-colors self-start sm:self-auto shadow-sm"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset Learned Profile</span>
              </button>
            )}
          </div>

          {!token ? (
            /* Unauthorized Prompt */
            <div className="p-12 text-center bg-white border border-[#DCD3C7] rounded-sm my-12 shadow-sm">
              <Brain className="w-12 h-12 text-[#8C2524] mx-auto mb-4 stroke-1" />
              <h2 className="font-editorial-heading font-bold text-2xl text-[#181615] mb-2">
                Sign In to View Your Dynamic Intelligence Profile
              </h2>
              <p className="font-editorial-body text-base text-[#6C645C] max-w-md mx-auto mb-6">
                Your active reading signals, topic growth, decay, and entity affinities continuously refine your daily personalized newspaper.
              </p>
              <button
                onClick={() => setShowAuthModal(true)}
                className="px-6 py-2.5 bg-[#181615] text-white text-xs font-bold uppercase tracking-widest hover:bg-[#8C2524] transition-colors rounded-sm"
              >
                Sign In / Register
              </button>
            </div>
          ) : loading ? (
            /* Loading Skeleton */
            <div className="space-y-8 animate-pulse py-4">
              <div className="h-24 bg-[#E8E1D5]/60 rounded-sm" />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="h-64 bg-white border border-[#E4DCCF] rounded-sm" />
                <div className="h-64 bg-white border border-[#E4DCCF] rounded-sm" />
              </div>
            </div>
          ) : profile ? (
            <div className="space-y-10">
              {/* Curation Intelligence Summary Banner */}
              <div className="p-5 bg-white border-2 border-[#181615] rounded-sm shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="w-6 h-6 text-emerald-700 shrink-0 mt-0.5" />
                  <div>
                    <h2 className="font-editorial-heading font-bold text-lg text-[#181615]">
                      Active Intelligence Summary
                    </h2>
                    <p className="font-editorial-body text-sm text-[#5C554E] mt-0.5">
                      {profile.summary}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs font-mono text-[#7A7268] shrink-0">
                  <span className="px-2.5 py-1 bg-[#F5EFEB] text-[#8C2524] font-bold rounded-sm uppercase tracking-wider">
                    {profile.explicit_interests.length} Explicit
                  </span>
                  <span className="px-2.5 py-1 bg-[#F5EFEB] text-[#181615] font-bold rounded-sm uppercase tracking-wider">
                    {profile.strong_interests.length + profile.emerging_interests.length + profile.stable_interests.length} Learned
                  </span>
                </div>
              </div>

              {/* Grid Section: Explicit Interests & Add Controls */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Column 1: Explicit User Interests */}
                <section className="lg:col-span-1 bg-white border border-[#DCD3C7] p-6 rounded-sm shadow-sm flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between border-b border-[#E4DCCF] pb-3 mb-4">
                      <div className="flex items-center gap-2">
                        <Sliders className="w-4 h-4 text-[#8C2524]" />
                        <h2 className="font-editorial-heading font-bold text-xl text-[#181615]">
                          Explicit Interests
                        </h2>
                      </div>
                      <span className="text-xs font-mono text-[#7A7268]">
                        Permanent
                      </span>
                    </div>

                    <p className="text-xs text-[#6C645C] mb-4">
                      Explicit topics you select remain stable and never decay automatically over time.
                    </p>

                    {profile.explicit_interests.length === 0 ? (
                      <div className="p-4 bg-[#FAF8F5] border border-dashed border-[#DCD3C7] text-center text-xs text-[#7A7268] rounded-sm mb-4">
                        No explicit interests set. Choose a topic below to anchor your daily edition.
                      </div>
                    ) : (
                      <div className="space-y-2.5 mb-6">
                        {profile.explicit_interests.map((item) => (
                          <div
                            key={item.topic_id}
                            className="p-3 bg-[#FAF8F5] border border-[#E5DDD0] rounded-sm flex items-center justify-between gap-2 hover:border-[#181615] transition-colors"
                          >
                            <div>
                              <span className="font-editorial-heading font-bold text-sm text-[#181615] block">
                                {item.name}
                              </span>
                              <span className="text-[10px] font-mono text-[#7A7268]">
                                Confidence: 100% • Explicit
                              </span>
                            </div>

                            <button
                              onClick={() => handleRemoveExplicitTopic(item.slug)}
                              className="p-1 text-stone-400 hover:text-rose-700 transition-colors"
                              title="Remove explicit interest"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Add Explicit Topic Form */}
                  <div className="pt-4 border-t border-[#E4DCCF]">
                    <label className="block text-[11px] font-bold uppercase tracking-wider text-[#181615] mb-1.5">
                      Add Explicit Topic
                    </label>
                    <div className="flex gap-2">
                      <select
                        value={selectedTopicSlug}
                        onChange={(e) => setSelectedTopicSlug(e.target.value)}
                        className="flex-1 px-3 py-1.5 text-xs bg-[#FAF8F5] border border-[#DCD3C7] rounded-sm focus:outline-none focus:border-[#181615] text-[#181615]"
                      >
                        <option value="">Select a topic...</option>
                        {allTopics
                          .filter(
                            (t) =>
                              !profile.explicit_interests.some(
                                (ei) => ei.slug === t.slug
                              )
                          )
                          .map((t) => (
                            <option key={t.id} value={t.slug}>
                              {t.name}
                            </option>
                          ))}
                      </select>
                      <button
                        onClick={handleAddExplicitTopic}
                        disabled={!selectedTopicSlug}
                        className="px-3 py-1.5 bg-[#181615] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] disabled:opacity-50 transition-colors rounded-sm inline-flex items-center gap-1"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Add</span>
                      </button>
                    </div>
                  </div>
                </section>

                {/* Column 2 & 3: Strong, Emerging, and Stable Learned Interests */}
                <div className="lg:col-span-2 space-y-6">
                  {/* Strong Interests */}
                  <section className="bg-white border border-[#DCD3C7] p-6 rounded-sm shadow-sm">
                    <div className="flex items-center justify-between border-b border-[#E4DCCF] pb-3 mb-4">
                      <div className="flex items-center gap-2">
                        <Flame className="w-5 h-5 text-[#8C2524]" />
                        <h2 className="font-editorial-heading font-bold text-xl text-[#181615]">
                          Strong & Established Interests
                        </h2>
                      </div>
                      <span className="text-xs font-mono text-[#7A7268]">
                        High Affinity
                      </span>
                    </div>

                    {profile.strong_interests.length === 0 ? (
                      <p className="text-xs text-[#7A7268] italic p-4 bg-[#FAF8F5] rounded-sm border border-dashed border-[#DCD3C7]">
                        No strong learned interests yet. Deep reading and saving articles will cultivate strong topic affinities.
                      </p>
                    ) : (
                      <div className="divide-y divide-[#E4DCCF]">
                        {profile.strong_interests.map((item) => (
                          <div
                            key={item.topic_id}
                            className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                          >
                            <div>
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className="font-editorial-heading font-bold text-base text-[#181615]">
                                  {item.name}
                                </span>
                                {item.parent_topic_name && (
                                  <span className="text-[10px] text-[#7A7268] font-mono">
                                    in {item.parent_topic_name}
                                  </span>
                                )}
                              </div>
                              <span className="text-[11px] font-mono text-[#6C645C]">
                                {item.evidence_count} interactions • Confidence: {Math.round(item.confidence * 100)}%
                              </span>
                            </div>

                            <div className="flex items-center gap-4">
                              {renderScoreBar(item.score)}
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleSuppressTopic(item.topic_id)}
                                  className="p-1.5 text-stone-400 hover:text-amber-700 transition-colors"
                                  title="Mark Not Interested"
                                >
                                  <Ban className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => handleRemoveLearnedTopic(item.topic_id)}
                                  className="p-1.5 text-stone-400 hover:text-rose-700 transition-colors"
                                  title="Remove from learned"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>

                  {/* Emerging Interests */}
                  <section className="bg-white border border-[#DCD3C7] p-6 rounded-sm shadow-sm">
                    <div className="flex items-center justify-between border-b border-[#E4DCCF] pb-3 mb-4">
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-emerald-600" />
                        <h2 className="font-editorial-heading font-bold text-xl text-[#181615]">
                          Emerging Interests
                        </h2>
                      </div>
                      <span className="text-xs font-mono text-emerald-700 font-bold">
                        Recent Momentum
                      </span>
                    </div>

                    {profile.emerging_interests.length === 0 ? (
                      <p className="text-xs text-[#7A7268] italic p-4 bg-[#FAF8F5] rounded-sm border border-dashed border-[#DCD3C7]">
                        No emerging interests currently detected. Exploring new topics will surface emerging trends here.
                      </p>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {profile.emerging_interests.map((item) => (
                          <div
                            key={item.topic_id}
                            className="p-3.5 bg-[#FAF8F5] border border-emerald-200 rounded-sm flex flex-col justify-between"
                          >
                            <div>
                              <div className="flex items-center justify-between gap-2 mb-1">
                                <span className="font-editorial-heading font-bold text-sm text-[#181615]">
                                  {item.name}
                                </span>
                                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full">
                                  Emerging
                                </span>
                              </div>
                              <p className="text-[11px] font-mono text-[#6C645C] mb-2">
                                {item.positive_count} recent positive signals
                              </p>
                            </div>

                            <div className="flex items-center justify-between pt-2 border-t border-[#E5DDD0]">
                              {renderScoreBar(item.score)}
                              <button
                                onClick={() => handleRemoveLearnedTopic(item.topic_id)}
                                className="text-[11px] text-[#7A7268] hover:text-rose-700 transition-colors"
                              >
                                Dismiss
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                </div>
              </div>

              {/* Bottom Multi-Section: Avoided Topics & Learned Subject Entities */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Avoided Topics (Negative Suppression) */}
                <section className="bg-white border border-[#DCD3C7] p-6 rounded-sm shadow-sm">
                  <div className="flex items-center justify-between border-b border-[#E4DCCF] pb-3 mb-4">
                    <div className="flex items-center gap-2">
                      <Ban className="w-5 h-5 text-rose-700" />
                      <h2 className="font-editorial-heading font-bold text-xl text-[#181615]">
                        Suppressed & Avoided Topics
                      </h2>
                    </div>
                    <span className="text-xs font-mono text-[#7A7268]">
                      Penalty Active
                    </span>
                  </div>

                  <p className="text-xs text-[#6C645C] mb-4">
                    Topics marked as &quot;Not Interested&quot; receive strong suppression in your daily editions and search ranking.
                  </p>

                  {profile.avoided_topics.length === 0 ? (
                    <p className="text-xs text-[#7A7268] italic p-4 bg-[#FAF8F5] rounded-sm border border-dashed border-[#DCD3C7]">
                      No topics currently suppressed.
                    </p>
                  ) : (
                    <div className="space-y-2.5">
                      {profile.avoided_topics.map((item) => (
                        <div
                          key={item.topic_id}
                          className="p-3 bg-rose-50/50 border border-rose-200 rounded-sm flex items-center justify-between gap-2"
                        >
                          <div>
                            <span className="font-editorial-heading font-bold text-sm text-[#181615] block">
                              {item.name}
                            </span>
                            <span className="text-[10px] font-mono text-rose-800">
                              Suppression: 100% penalty
                            </span>
                          </div>

                          <button
                            onClick={() => handleRestoreAvoidedTopic(item.topic_id)}
                            className="px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-[#181615] bg-white border border-[#DCD3C7] hover:bg-white/80 rounded-sm transition-colors"
                          >
                            Restore
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                {/* Learned Subject Entities */}
                <section className="bg-white border border-[#DCD3C7] p-6 rounded-sm shadow-sm">
                  <div className="flex items-center justify-between border-b border-[#E4DCCF] pb-3 mb-4">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-[#8C2524]" />
                      <h2 className="font-editorial-heading font-bold text-xl text-[#181615]">
                        Learned Subject Entities
                      </h2>
                    </div>
                    <span className="text-xs font-mono text-[#7A7268]">
                      Affinities
                    </span>
                  </div>

                  <p className="text-xs text-[#6C645C] mb-4">
                    Specific organizations, technologies, and figures frequently surfaced in your completed reads.
                  </p>

                  {profile.top_entities.length === 0 ? (
                    <p className="text-xs text-[#7A7268] italic p-4 bg-[#FAF8F5] rounded-sm border border-dashed border-[#DCD3C7]">
                      No entity affinities extracted yet. Reading stories with prominent entities will populate this section.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {profile.top_entities.map((e) => (
                        <div
                          key={e.entity_id}
                          className="px-3 py-1.5 bg-[#FAF8F5] border border-[#DCD3C7] rounded-sm flex items-center gap-2"
                        >
                          <span className="font-semibold text-xs text-[#181615]">
                            {e.name}
                          </span>
                          <span className="text-[10px] font-mono font-bold text-[#8C2524]">
                            {Math.round(e.score * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            </div>
          ) : null}
        </main>
      </div>

      <Footer />

      {/* Reset Confirmation Modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white border-2 border-[#181615] max-w-md w-full p-6 rounded-sm shadow-2xl font-sans">
            <div className="flex items-center gap-3 text-rose-700 mb-3">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="font-editorial-heading font-bold text-xl text-[#181615]">
                Reset Learned Interests?
              </h3>
            </div>

            <p className="text-xs text-[#5C554E] leading-relaxed mb-4">
              This will clear all automatically learned topics, inferred interests, entity affinities, and cached semantic vectors.
            </p>

            <div className="p-3 bg-[#FAF8F5] border border-[#E5DDD0] rounded-sm text-xs text-[#181615] font-semibold flex items-center gap-2 mb-6">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                Your {profile?.explicit_interests.length || 0} explicitly chosen interests will remain completely intact.
              </span>
            </div>

            <div className="flex items-center justify-end gap-3 font-sans text-xs">
              <button
                onClick={() => setShowResetConfirm(false)}
                disabled={isResetting}
                className="px-4 py-2 border border-[#DCD3C7] text-[#181615] font-bold uppercase tracking-wider hover:bg-[#FAF8F5] rounded-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleResetLearned}
                disabled={isResetting}
                className="px-4 py-2 bg-rose-700 text-white font-bold uppercase tracking-wider hover:bg-rose-800 disabled:opacity-50 rounded-sm"
              >
                {isResetting ? "Resetting..." : "Confirm Reset"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Auth & Preferences Modals */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={(newToken, newUser) => {
          localStorage.setItem("pn_auth_token", newToken);
          setToken(newToken);
          setUser(newUser);
          setShowAuthModal(false);
        }}
      />

      {token && (
        <MyInterestsModal
          isOpen={showInterestsModal}
          onClose={() => setShowInterestsModal(false)}
          token={token}
        />
      )}
    </div>
  );
}
