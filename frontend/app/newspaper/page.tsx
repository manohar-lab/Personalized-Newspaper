"use client";

import React, { useEffect, useState, useMemo } from "react";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { CurationBanner } from "@/components/CurationBanner";
import { FeaturedArticle } from "@/components/FeaturedArticle";
import { ArticleSection } from "@/components/ArticleSection";
import { NewspaperSkeleton } from "@/components/NewspaperSkeleton";
import { EmptyNewspaperState } from "@/components/EmptyNewspaperState";
import { AuthModal } from "@/components/AuthModal";
import { Onboarding } from "@/components/Onboarding";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Footer } from "@/components/Footer";
import {
  fetchCurrentUser,
  fetchPersonalizedNewspaper,
  fetchArticles,
  fetchFeaturedArticle,
} from "@/lib/api";
import { User, NewspaperResponse, Article, TopicSummary } from "@/types";

export default function NewspaperPage() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [newspaperData, setNewspaperData] = useState<NewspaperResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
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
      loadUserAndNewspaper(savedToken);
    } else {
      loadPublicNewspaper();
    }
  }, []);

  const loadUserAndNewspaper = async (authToken: string) => {
    setLoading(true);
    setError(null);
    try {
      const u = await fetchCurrentUser(authToken);
      setUser(u);
      const data = await fetchPersonalizedNewspaper(authToken);
      setNewspaperData(data);
    } catch (err: any) {
      console.warn("Personalized fetch error, falling back to public feed:", err);
      // If token invalid, clear it
      if (err?.message?.includes("credentials") || err?.message?.includes("401")) {
        localStorage.removeItem("pn_auth_token");
        setToken(null);
        setUser(null);
      }
      await loadPublicNewspaper();
    } finally {
      setLoading(false);
    }
  };

  const loadPublicNewspaper = async () => {
    setLoading(true);
    setError(null);
    try {
      const articlesResp = await fetchArticles({ limit: 20 });
      const featured = articlesResp.items.length > 0 ? articlesResp.items[0] : null;

      // Group articles by topic
      const topicMap = new Map<string, { topic: TopicSummary; articles: Article[] }>();
      for (const art of articlesResp.items) {
        for (const t of art.topics) {
          if (!topicMap.has(t.slug)) {
            topicMap.set(t.slug, { topic: t, articles: [] });
          }
          topicMap.get(t.slug)!.articles.push(art);
        }
      }

      const sections = Array.from(topicMap.values()).map((v) => ({
        topic: v.topic,
        total_articles: v.articles.length,
        articles: v.articles,
      }));

      const todayStr = new Date().toLocaleDateString("en-US", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });

      setNewspaperData({
        edition: {
          date: todayStr,
          title: "The Personalized Chronicle",
          subtitle: "General Public Edition",
        },
        user: {
          id: "guest",
          name: "Guest Reader",
          email: "",
        },
        curation_summary: "Welcome to the digital newspaper. Sign in to curate your edition.",
        has_interests: false,
        featured_article: featured,
        sections,
      });
    } catch (err: any) {
      setError(err?.message || "Failed to load newspaper edition");
    } finally {
      setLoading(false);
    }
  };

  const handleAuthSuccess = (newToken: string, newUser: User) => {
    localStorage.setItem("pn_auth_token", newToken);
    setToken(newToken);
    setUser(newUser);
    setShowAuthModal(false);
    loadUserAndNewspaper(newToken);
  };

  const handleSignOut = () => {
    localStorage.removeItem("pn_auth_token");
    setToken(null);
    setUser(null);
    loadPublicNewspaper();
  };

  const handleOnboardingComplete = () => {
    setShowOnboarding(false);
    if (token) {
      loadUserAndNewspaper(token);
    }
  };

  const handleActionComplete = (action: string, articleId: string) => {
    if (action === "NOT_INTERESTED" && newspaperData) {
      // Remove story from sections and lead in state
      const updatedSections = newspaperData.sections.map((sec) => ({
        ...sec,
        articles: sec.articles.filter((a) => a.id !== articleId),
      })).filter((sec) => sec.articles.length > 0);

      const updatedFeatured =
        newspaperData.featured_article?.id === articleId
          ? null
          : newspaperData.featured_article;

      setNewspaperData({
        ...newspaperData,
        featured_article: updatedFeatured,
        sections: updatedSections,
      });
    }
  };

  // Filter sections by search query if user typed search
  const filteredSections = useMemo(() => {
    if (!newspaperData || !searchQuery.trim()) return newspaperData?.sections || [];
    const q = searchQuery.toLowerCase();
    return newspaperData.sections
      .map((sec) => ({
        ...sec,
        articles: sec.articles.filter(
          (a) =>
            a.title.toLowerCase().includes(q) ||
            a.description?.toLowerCase().includes(q) ||
            a.topics.some((t) => t.name.toLowerCase().includes(q))
        ),
      }))
      .filter((sec) => sec.articles.length > 0);
  }, [newspaperData, searchQuery]);

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

        {/* Curation Top Greeting Banner */}
        {user && newspaperData && (
          <CurationBanner
            userName={user.full_name || user.email.split("@")[0]}
            curationSummary={newspaperData.curation_summary}
            hasInterests={newspaperData.has_interests}
            onEditInterests={() => setShowInterestsModal(true)}
            onOpenOnboarding={() => setShowOnboarding(true)}
          />
        )}

        {/* Main Content Area */}
        <main className="max-w-7xl mx-auto px-4 sm:px-8 py-6">
          {loading ? (
            <NewspaperSkeleton />
          ) : error ? (
            <EmptyNewspaperState
              type="error"
              errorMessage={error}
              onRetry={() => (token ? loadUserAndNewspaper(token) : loadPublicNewspaper())}
            />
          ) : user && !newspaperData?.has_interests ? (
            <EmptyNewspaperState
              type="no_interests"
              onOpenOnboarding={() => setShowOnboarding(true)}
            />
          ) : !newspaperData?.featured_article && filteredSections.length === 0 ? (
            <EmptyNewspaperState
              type="no_articles"
              onRetry={() => (token ? loadUserAndNewspaper(token) : loadPublicNewspaper())}
            />
          ) : (
            <>
              {/* Lead Story */}
              {newspaperData?.featured_article && !searchQuery && (
                <FeaturedArticle
                  article={newspaperData.featured_article}
                  token={token}
                  onActionComplete={handleActionComplete}
                />
              )}

              {/* Dynamic News Sections based on user's interests */}
              <div className="mt-8">
                {filteredSections.map((sec) => (
                  <ArticleSection
                    key={sec.topic.slug}
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
            if (token) loadUserAndNewspaper(token);
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
