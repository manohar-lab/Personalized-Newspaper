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
import {
  fetchCurrentUser,
  fetchTodayEdition,
  regenerateTodayEdition,
} from "@/lib/api";
import { User, NewspaperEditionResponse } from "@/types";
import { RefreshCw, Sparkles, Calendar, Layers } from "lucide-react";

export default function NewspaperPage() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [edition, setEdition] = useState<NewspaperEditionResponse | null>(null);
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
    setError(null);
    try {
      const u = await fetchCurrentUser(authToken);
      setUser(u);
      const ed = await fetchTodayEdition(authToken);
      setEdition(ed);
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
    }
  };

  const handleRegenerate = async () => {
    if (!token) return;
    setRegenerating(true);
    try {
      const refreshed = await regenerateTodayEdition(token);
      setEdition(refreshed);
    } catch (err: any) {
      alert("Failed to regenerate edition: " + (err?.message || "Server error"));
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
      // Remove story from sections and lead in local state
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

  // Filter sections by search query
  const filteredSections = useMemo(() => {
    if (!edition || !searchQuery.trim()) return edition?.sections || [];
    const q = searchQuery.toLowerCase();
    return edition.sections
      .map((sec) => ({
        ...sec,
        stories: sec.stories.filter(
          (s) =>
            s.title.toLowerCase().includes(q) ||
            s.summary?.toLowerCase().includes(q) ||
            s.topics.some((t) => t.toLowerCase().includes(q))
        ),
      }))
      .filter((sec) => sec.stories.length > 0);
  }, [edition, searchQuery]);

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

        {/* Masthead Banner & Subtitle */}
        {edition && (
          <div className="bg-[#F3EFE6] border-b border-[#E0D8C8]">
            <div className="max-w-7xl mx-auto px-4 sm:px-8 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-[#7A7268]">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>{formattedDate}</span>
                  <span>•</span>
                  <span>{edition.title || "YOUR DAILY"}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5" />
                    {edition.total_stories} stories
                  </span>
                </div>
                {edition.subtitle && (
                  <p className="font-editorial-body text-sm text-[#4E473F] mt-1 italic">
                    {edition.subtitle}
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleRegenerate}
                  disabled={regenerating}
                  className="px-3.5 py-1.5 bg-white hover:bg-[#FAF8F5] border border-[#181615] text-[#181615] text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm transition-all disabled:opacity-50"
                  title="Regenerate today's edition with updated interests"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${regenerating ? "animate-spin" : ""}`} />
                  <span>{regenerating ? "Regenerating..." : "Regenerate"}</span>
                </button>

                <button
                  onClick={() => setShowInterestsModal(true)}
                  className="px-3.5 py-1.5 bg-[#181615] hover:bg-[#8C2524] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-sm transition-all"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Edit Interests</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <main className="max-w-7xl mx-auto px-4 sm:px-8 py-6">
          {loading ? (
            <NewspaperSkeleton />
          ) : error ? (
            <EmptyNewspaperState
              type="error"
              errorMessage={error}
              onRetry={() => (token ? loadUserAndEdition(token) : setShowAuthModal(true))}
            />
          ) : !edition?.lead_story && filteredSections.length === 0 ? (
            <EmptyNewspaperState
              type="no_articles"
              onRetry={() => (token ? loadUserAndEdition(token) : setShowAuthModal(true))}
            />
          ) : (
            <>
              {/* User-Specific Lead Story */}
              {edition?.lead_story && !searchQuery && (
                <EditionStoryCard
                  story={edition.lead_story}
                  token={token}
                  layout="LEAD"
                  onActionComplete={handleActionComplete}
                />
              )}

              {/* Controlled Editorial Sections */}
              <div className="mt-8">
                {filteredSections.map((sec) => (
                  <EditionSection
                    key={sec.name}
                    section={sec}
                    token={token}
                    onActionComplete={handleActionComplete}
                  />
                ))}
              </div>
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
