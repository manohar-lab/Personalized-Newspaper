"use client";

import React, { useEffect, useState, useMemo } from "react";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { EditionStoryCard } from "@/components/EditionStoryCard";
import { EditionSection } from "@/components/EditionSection";
import { NewspaperSkeleton } from "@/components/NewspaperSkeleton";
import { EmptyNewspaperState } from "@/components/EmptyNewspaperState";
import { AuthModal } from "@/components/AuthModal";
import { Onboarding } from "@/components/Onboarding";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Footer } from "@/components/Footer";
import { DailyBriefingHero } from "@/components/DailyBriefingHero";
import {
  fetchCurrentUser,
  fetchTodayEdition,
  regenerateTodayEdition,
  fetchTodayBriefing,
  generateBriefing,
  startNewsSession,
  sendSessionHeartbeat,
  endNewsSession,
} from "@/lib/api";
import { User, NewspaperEditionResponse, NewspaperSectionResponse, NewsBriefingResponse } from "@/types";
import { RefreshCw, Sparkles, Calendar, Layers, Newspaper, Compass, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function NewspaperPage() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [edition, setEdition] = useState<NewspaperEditionResponse | null>(null);
  const [briefing, setBriefing] = useState<NewsBriefingResponse | null>(null);
  const [briefingLoading, setBriefingLoading] = useState<boolean>(true);
  const [briefingRefreshing, setBriefingRefreshing] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [regenerating, setRegenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modals state
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [showOnboarding, setShowOnboarding] = useState<boolean>(false);
  const [showInterestsModal, setShowInterestsModal] = useState<boolean>(false);

  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token");
    if (savedToken) {
      setToken(savedToken);
      loadUserAndEdition(savedToken);
    } else {
      setLoading(false);
      setShowAuthModal(true);
    }
  }, []);

  const loadUserAndEdition = async (authToken: string) => {
    setLoading(true);
    setBriefingLoading(true);
    setError(null);
    try {
      const u = await fetchCurrentUser(authToken);
      setUser(u);

      // Start news session
      try {
        const sess = await startNewsSession(authToken);
        setSessionId(sess.session_id);
      } catch (sessErr) {
        console.warn("Could not start session:", sessErr);
      }

      // Fetch edition and briefing in parallel
      const [ed, br] = await Promise.allSettled([
        fetchTodayEdition(authToken),
        fetchTodayBriefing(authToken),
      ]);

      if (ed.status === "fulfilled") {
        setEdition(ed.value);
      } else {
        throw ed.reason;
      }

      if (br.status === "fulfilled") {
        setBriefing(br.value);
      }
    } catch (err: any) {
      console.warn("Error fetching newspaper edition:", err);
      if (err?.message?.includes("credentials") || err?.message?.includes("401")) {
        localStorage.removeItem("pn_auth_token");
        setToken(null);
        setUser(null);
        setShowAuthModal(true);
      } else {
        setError(err?.message || "Failed to load newspaper edition");
      }
    } finally {
      setLoading(false);
      setBriefingLoading(false);
    }
  };

  const handleRefreshBriefing = async () => {
    if (!token) return;
    setBriefingRefreshing(true);
    try {
      const refreshed = await generateBriefing(token, true);
      setBriefing(refreshed);
    } catch (err: any) {
      console.warn("Failed to refresh briefing:", err);
    } finally {
      setBriefingRefreshing(false);
    }
  };

  const handleRegenerate = async () => {
    if (!token) return;
    setRegenerating(true);
    try {
      const refreshed = await regenerateTodayEdition(token);
      setEdition(refreshed);
    } catch (err: any) {
      alert("Failed to refresh edition: " + (err?.message || "Server error"));
    } finally {
      setRegenerating(false);
    }
  };

  const handleAuthSuccess = (newToken: string, newUser: User) => {
    localStorage.setItem("pn_auth_token", newToken);
    setToken(newToken);
    setUser(newUser);
    setShowAuthModal(false);
    loadUserAndEdition(newToken);
  };

  const handleSignOut = () => {
    localStorage.removeItem("pn_auth_token");
    setToken(null);
    setUser(null);
    setEdition(null);
    setShowAuthModal(true);
  };

  const handleOnboardingComplete = () => {
    setShowOnboarding(false);
    if (token) {
      handleRegenerate();
    }
  };

  const handleActionComplete = (action: string, articleId: string) => {
    if (action === "NOT_INTERESTED" && edition) {
      const updatedSections = edition.sections.map((sec) => ({
        ...sec,
        stories: sec.stories.filter((s) => s.article_id !== articleId),
        story_count: sec.stories.filter((s) => s.article_id !== articleId).length,
      })).filter((sec) => sec.stories.length > 0);

      const updatedLead =
        edition.lead_story?.article_id === articleId ? null : edition.lead_story;

      setEdition({
        ...edition,
        lead_story: updatedLead,
        sections: updatedSections,
        total_stories: Math.max(0, edition.total_stories - 1),
      });
    }
  };

  // Split sections for broadsheet layout
  const { topStoriesSection, forYouSection, discoverSection, domainSections } = useMemo(() => {
    if (!edition?.sections) {
      return { topStoriesSection: null, forYouSection: null, discoverSection: null, domainSections: [] };
    }

    let topStories: NewspaperSectionResponse | null = null;
    let forYou: NewspaperSectionResponse | null = null;
    let discover: NewspaperSectionResponse | null = null;
    const domains: NewspaperSectionResponse[] = [];

    for (const sec of edition.sections) {
      const normName = sec.name.toUpperCase().replace(" ", "_");
      if (normName === "TOP_STORIES") {
        topStories = sec;
      } else if (normName === "FOR_YOU") {
        forYou = sec;
      } else if (normName === "DISCOVER") {
        discover = sec;
      } else {
        domains.push(sec);
      }
    }

    return { topStoriesSection: topStories, forYouSection: forYou, discoverSection: discover, domainSections: domains };
  }, [edition?.sections]);

  const formattedDate = useMemo(() => {
    if (!edition?.edition_date) {
      return new Date().toLocaleDateString("en-US", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    }
    const [year, month, day] = edition.edition_date.split("-").map(Number);
    const d = new Date(Date.UTC(year, month - 1, day));
    return d.toLocaleDateString("en-US", {
      timeZone: "UTC",
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }, [edition?.edition_date]);

  return (
    <div className="min-h-screen flex flex-col justify-between bg-[#FAF8F5] text-[#181615]">
      <div>
        <NewspaperHeader
          user={user}
          onOpenAuth={() => setShowAuthModal(true)}
          onOpenInterests={() => {
            if (!token) setShowAuthModal(true);
            else setShowInterestsModal(true);
          }}
          onSignOut={handleSignOut}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        {/* Masthead Banner & Editorial Summary */}
        {edition && (
          <div className="bg-[#F3EFE6] border-b border-[#E0D8C8]">
            <div className="max-w-7xl mx-auto px-4 sm:px-8 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-widest text-[#7A7268]">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>{formattedDate}</span>
                  <span>•</span>
                  <span>{edition.title || "PERSONAL DAILY"}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5" />
                    {edition.total_stories} stories
                  </span>
                  {edition.subtitle && (
                    <>
                      <span>•</span>
                      <span className="text-[#8C2524] font-bold">{edition.subtitle}</span>
                    </>
                  )}
                </div>

                {edition.curation_summary && (
                  <p className="font-editorial-body text-sm sm:text-base text-[#3A332C] mt-1.5 italic max-w-4xl leading-relaxed">
                    &ldquo;{edition.curation_summary}&rdquo;
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleRegenerate}
                  disabled={regenerating}
                  className="px-3.5 py-1.5 bg-white hover:bg-[#FAF8F5] border border-[#181615] text-[#181615] text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-50"
                  title="Refresh edition with new updates"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${regenerating ? "animate-spin" : ""}`} />
                  <span>{regenerating ? "Updating..." : "Refresh Edition"}</span>
                </button>

                <button
                  onClick={() => setShowInterestsModal(true)}
                  className="px-3.5 py-1.5 bg-[#181615] hover:bg-[#8C2524] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm transition-all"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>My Interests</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Broadsheet Area */}
        <main className="max-w-7xl mx-auto px-4 sm:px-8 py-6">
          {loading ? (
            <NewspaperSkeleton />
          ) : error ? (
            <EmptyNewspaperState
              type="error"
              errorMessage={error}
              onRetry={() => (token ? loadUserAndEdition(token) : setShowAuthModal(true))}
            />
          ) : !edition?.lead_story && (!edition?.sections || edition.sections.length === 0) ? (
            <EmptyNewspaperState
              type="no_articles"
              onRetry={() => (token ? loadUserAndEdition(token) : setShowAuthModal(true))}
            />
          ) : (
            <>
              {/* PHASE 18: PERSONAL NEWS BRIEFING HERO */}
              {!searchQuery && (
                <DailyBriefingHero
                  briefing={briefing}
                  loading={briefingLoading}
                  onRefresh={handleRefreshBriefing}
                  refreshing={briefingRefreshing}
                />
              )}

              {/* 1. LEAD STORY */}
              {edition?.lead_story && !searchQuery && (
                <EditionStoryCard
                  story={edition.lead_story}
                  token={token}
                  layout="LEAD"
                  onActionComplete={handleActionComplete}
                />
              )}

              {/* 2. BROADSHEET SPLIT: TOP STORIES & FOR YOU */}
              {(topStoriesSection || forYouSection) && !searchQuery && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-10 pb-8 border-b-2 border-[#181615]">
                  {/* Top Stories Column */}
                  {topStoriesSection && (
                    <div className={forYouSection ? "lg:col-span-7" : "lg:col-span-12"}>
                      <div className="flex items-baseline justify-between pb-2 mb-4 border-b-2 border-[#181615]">
                        <h2 className="font-editorial-heading font-black text-xl text-[#181615] uppercase tracking-wider">
                          Top Stories
                        </h2>
                        <span className="text-xs text-[#7A7268]">
                          {topStoriesSection.stories.length} stories
                        </span>
                      </div>
                      <div className="flex flex-col divide-y divide-[#E8E1D5]">
                        {topStoriesSection.stories.map((story) => (
                          <EditionStoryCard
                            key={story.id}
                            story={story}
                            token={token}
                            layout={story.layout_type === "FEATURE" ? "FEATURE" : "STANDARD"}
                            onActionComplete={handleActionComplete}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* For You Column */}
                  {forYouSection && (
                    <div className={topStoriesSection ? "lg:col-span-5 bg-[#FAF3EA] p-5 border border-[#E8DDCF] rounded-sm self-start" : "lg:col-span-12"}>
                      <div className="flex items-baseline justify-between pb-2 mb-4 border-b border-[#D8CCBD]">
                        <div className="flex items-center gap-1.5">
                          <Sparkles className="w-4 h-4 text-[#8C2524]" />
                          <h2 className="font-editorial-heading font-black text-xl text-[#8C2524] uppercase tracking-wider">
                            For You
                          </h2>
                        </div>
                        <span className="text-xs text-[#7A7268]">
                          {forYouSection.stories.length} stories
                        </span>
                      </div>
                      <div className="flex flex-col divide-y divide-[#EADFCF]">
                        {forYouSection.stories.map((story) => (
                          <EditionStoryCard
                            key={story.id}
                            story={story}
                            token={token}
                            layout="STANDARD"
                            onActionComplete={handleActionComplete}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 3. DOMAIN EDITORIAL SECTIONS (Technology, Business, Science, World, etc.) */}
              <div className="mt-8">
                {domainSections.map((sec) => (
                  <EditionSection
                    key={sec.name}
                    section={sec}
                    token={token}
                    onActionComplete={handleActionComplete}
                  />
                ))}
              </div>

              {/* 4. DISCOVER SECTION */}
              {discoverSection && discoverSection.stories.length > 0 && !searchQuery && (
                <section className="mt-12 mb-8 bg-[#F5F2EC] border-2 border-[#181615] p-6 sm:p-8">
                  <div className="flex items-center justify-between pb-3 mb-6 border-b border-[#DCD4C7]">
                    <div className="flex items-center gap-2">
                      <Compass className="w-5 h-5 text-[#8C2524]" />
                      <h2 className="font-editorial-heading font-black text-xl sm:text-2xl text-[#181615] uppercase tracking-wider">
                        Discover Something New
                      </h2>
                    </div>
                    <Link
                      href="/discover"
                      className="text-xs font-bold uppercase tracking-wider text-[#8C2524] hover:underline flex items-center gap-1"
                    >
                      <span>Explore More</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {discoverSection.stories.map((story) => (
                      <EditionStoryCard
                        key={story.id}
                        story={story}
                        token={token}
                        layout="FEATURE"
                        onActionComplete={handleActionComplete}
                      />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </main>
      </div>

      <Footer />

      {/* Modals */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={handleAuthSuccess}
      />

      {token && (
        <MyInterestsModal
          isOpen={showInterestsModal}
          onClose={() => {
            setShowInterestsModal(false);
            if (token) loadUserAndEdition(token);
          }}
          token={token}
        />
      )}

      {showOnboarding && token && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-[#FAF8F5] border-2 border-[#181615] max-w-4xl w-full my-8 p-6 sm:p-10 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowOnboarding(false)}
              className="absolute top-4 right-4 text-[#7A7268] hover:text-[#181615] font-bold text-sm px-2 py-1"
            >
              ✕ Close
            </button>
            <Onboarding
              token={token}
              onComplete={handleOnboardingComplete}
            />
          </div>
        </div>
      )}
    </div>
  );
}
