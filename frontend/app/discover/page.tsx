"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { AuthModal } from "@/components/AuthModal";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Footer } from "@/components/Footer";
import {
  fetchCurrentUser,
  fetchRecommendations,
  recordRecommendationInteraction,
} from "@/lib/api";
import { User, RecommendationItem, RecommendationFeedResponse } from "@/types";
import {
  Compass,
  TrendingUp,
  Sparkles,
  Clock,
  ChevronRight,
  RefreshCw,
  Star,
  BookOpen,
  Zap,
  Eye,
  ArrowRight,
} from "lucide-react";

// ─── Recommendation Card ────────────────────────────────────────────────────
function RecommendationCard({
  item,
  token,
  onImpression,
}: {
  item: RecommendationItem;
  token: string | null;
  onImpression?: (articleId: string) => void;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const impressionSent = useRef(false);

  // Intersection Observer for impression tracking
  useEffect(() => {
    if (!cardRef.current || impressionSent.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !impressionSent.current) {
          impressionSent.current = true;
          onImpression?.(item.article_id);
        }
      },
      { threshold: 0.5 }
    );
    observer.observe(cardRef.current);
    return () => observer.disconnect();
  }, [item.article_id, onImpression]);

  const handleClick = () => {
    if (token) {
      recordRecommendationInteraction(item.article_id, "CLICK", token, "DISCOVER").catch(
        () => {}
      );
    }
  };

  const reasonIcon =
    item.reason_type === "TRENDING_FOR_YOU" ? (
      <TrendingUp className="w-3 h-3" />
    ) : item.reason_type === "DISCOVERY" ? (
      <Compass className="w-3 h-3" />
    ) : item.reason_type === "EMERGING_INTEREST" ? (
      <Zap className="w-3 h-3" />
    ) : (
      <Star className="w-3 h-3" />
    );

  return (
    <div
      ref={cardRef}
      className="group bg-white border border-[#E4DCCF] hover:border-[#181615] transition-all duration-300 hover:shadow-lg flex flex-col"
    >
      {/* Image */}
      {item.image && (
        <Link href={`/article/${item.article_id}?source=RECOMMENDATION`} onClick={handleClick}>
          <div className="aspect-[16/9] overflow-hidden bg-[#E8E1D5]">
            <img
              src={item.image}
              alt={item.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            />
          </div>
        </Link>
      )}

      <div className="p-4 sm:p-5 flex flex-col flex-1">
        {/* Reason Badge */}
        <div className="flex items-center gap-1.5 mb-2.5">
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-[#8C2524] font-sans">
            {reasonIcon}
            {item.reason_text}
          </span>
        </div>

        {/* Title */}
        <Link href={`/article/${item.article_id}?source=RECOMMENDATION`} onClick={handleClick}>
          <h3 className="font-editorial-heading font-bold text-lg sm:text-xl text-[#110F0E] leading-tight mb-2 group-hover:text-[#8C2524] transition-colors line-clamp-3">
            {item.title}
          </h3>
        </Link>

        {/* Summary */}
        {item.summary && (
          <p className="font-editorial-body text-sm text-[#4E473F] leading-relaxed mb-3 line-clamp-2 flex-1">
            {item.summary}
          </p>
        )}

        {/* Meta */}
        <div className="flex items-center justify-between mt-auto pt-3 border-t border-[#ECE5DA] text-[11px] font-sans text-[#7A7268]">
          <div className="flex items-center gap-2">
            {item.source && (
              <span className="font-semibold text-[#181615]">{item.source}</span>
            )}
            {item.published_at && (
              <>
                <span className="text-[#B5ABA0]">•</span>
                <span>
                  {new Date(item.published_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {item.reading_time && (
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {item.reading_time} min
              </span>
            )}
            {item.is_new && (
              <span className="ml-1 px-1.5 py-0.5 bg-[#8C2524] text-white text-[9px] font-bold uppercase tracking-wider rounded-sm">
                New
              </span>
            )}
            {item.is_read && (
              <span className="ml-1 px-1.5 py-0.5 bg-[#E4DCCF] text-[#5C554E] text-[9px] font-bold uppercase tracking-wider rounded-sm">
                Read
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Section Component ──────────────────────────────────────────────────────
function DiscoverSection({
  title,
  icon,
  items,
  token,
  onImpression,
  accentColor,
}: {
  title: string;
  icon: React.ReactNode;
  items: RecommendationItem[];
  token: string | null;
  onImpression: (articleId: string) => void;
  accentColor?: string;
}) {
  if (!items || items.length === 0) return null;

  return (
    <section className="mb-12">
      {/* Section Header */}
      <div className="flex items-center justify-between mb-6 pb-3 border-b-2 border-[#181615]">
        <div className="flex items-center gap-2.5">
          <span className={`${accentColor || "text-[#8C2524]"}`}>{icon}</span>
          <h2 className="font-editorial-heading font-bold text-xl sm:text-2xl text-[#110F0E]">
            {title}
          </h2>
        </div>
        <span className="text-xs font-mono uppercase tracking-wider text-[#7A7268] font-sans">
          {items.length} {items.length === 1 ? "story" : "stories"}
        </span>
      </div>

      {/* Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {items.map((item) => (
          <RecommendationCard
            key={item.article_id}
            item={item}
            token={token}
            onImpression={onImpression}
          />
        ))}
      </div>
    </section>
  );
}

// ─── Empty State ────────────────────────────────────────────────────────────
function EmptyDiscoverState() {
  return (
    <div className="py-16 text-center">
      <div className="inline-flex items-center justify-center w-20 h-20 bg-[#F5EFEB] border-2 border-[#DCD3C7] rounded-full mb-6">
        <Compass className="w-10 h-10 text-[#8C2524]" />
      </div>
      <h2 className="font-editorial-heading font-bold text-2xl sm:text-3xl text-[#110F0E] mb-3">
        Your Discovery Feed is Being Prepared
      </h2>
      <p className="font-editorial-body text-base text-[#5C554E] max-w-lg mx-auto mb-6 leading-relaxed">
        As you read articles and explore topics, we&apos;ll curate a personalized
        discovery feed tailored to your interests and reading patterns.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center font-sans">
        <Link
          href="/newspaper"
          className="inline-flex items-center gap-2 px-6 py-3 bg-[#181615] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors"
        >
          <BookOpen className="w-4 h-4" />
          Read Today&apos;s Edition
        </Link>
        <Link
          href="/interests"
          className="inline-flex items-center gap-2 px-6 py-3 bg-white border-2 border-[#181615] text-[#181615] text-xs font-bold uppercase tracking-wider hover:bg-[#F5EFEB] transition-colors"
        >
          <Sparkles className="w-4 h-4" />
          Set Your Interests
        </Link>
      </div>
    </div>
  );
}

// ─── Main Discover Page ─────────────────────────────────────────────────────
export default function DiscoverPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [feed, setFeed] = useState<RecommendationFeedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showInterestsModal, setShowInterestsModal] = useState(false);

  // Auth check
  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token");
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser(savedToken)
        .then(setUser)
        .catch(() => {});
    }
  }, []);

  // Load recommendations
  const loadRecommendations = useCallback(
    async (forceRefresh = false) => {
      if (forceRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const data = await fetchRecommendations(
          token || undefined,
          30,
          1,
          "DISCOVER",
          forceRefresh
        );
        setFeed(data);
      } catch (err: any) {
        setError(err?.message || "Failed to load recommendations");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token]
  );

  useEffect(() => {
    loadRecommendations();
  }, [loadRecommendations]);

  // Impression tracker
  const handleImpression = useCallback(
    (articleId: string) => {
      if (token) {
        recordRecommendationInteraction(articleId, "IMPRESSION", token, "DISCOVER").catch(
          () => {}
        );
      }
    },
    [token]
  );

  const hasRecommendations =
    feed &&
    (feed.recommended_for_you.length > 0 ||
      feed.trending_in_your_interests.length > 0 ||
      feed.discover_something_new.length > 0 ||
      feed.recommendations.length > 0);

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

        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-8">
          {/* Page Header */}
          <div className="text-center mb-10 pb-6 border-b-2 border-[#181615]">
            <div className="flex items-center justify-center gap-3 mb-3">
              <Compass className="w-7 h-7 text-[#8C2524]" />
              <h1 className="font-editorial-masthead text-3xl sm:text-4xl lg:text-5xl font-black text-[#110F0E] uppercase tracking-tight">
                Discover For You
              </h1>
            </div>
            <p className="font-editorial-heading italic text-sm sm:text-base text-[#6C645C] max-w-2xl mx-auto">
              Personalized stories you haven&apos;t seen yet — curated from your
              interests, reading patterns, and emerging topics
            </p>

            {/* Refresh button */}
            <button
              onClick={() => loadRecommendations(true)}
              disabled={refreshing}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-white border border-[#DCD3C7] text-xs font-bold uppercase tracking-wider text-[#181615] hover:border-[#181615] hover:bg-[#F5EFEB] transition-colors font-sans disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh Recommendations"}
            </button>
          </div>

          {/* Loading Skeleton */}
          {loading && (
            <div className="space-y-10 animate-pulse">
              <div>
                <div className="h-6 w-56 bg-[#E5DDD0] rounded mb-6" />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="bg-white border border-[#E4DCCF]">
                      <div className="aspect-[16/9] bg-[#E8E1D5]" />
                      <div className="p-5 space-y-3">
                        <div className="h-3 w-32 bg-[#E5DDD0] rounded" />
                        <div className="h-5 w-full bg-[#DCD3C7] rounded" />
                        <div className="h-4 w-3/4 bg-[#E5DDD0] rounded" />
                        <div className="h-3 w-24 bg-[#E5DDD0] rounded" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="h-6 w-44 bg-[#E5DDD0] rounded mb-6" />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="bg-white border border-[#E4DCCF]">
                      <div className="p-5 space-y-3">
                        <div className="h-3 w-28 bg-[#E5DDD0] rounded" />
                        <div className="h-5 w-full bg-[#DCD3C7] rounded" />
                        <div className="h-4 w-5/6 bg-[#E5DDD0] rounded" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && !loading && (
            <div className="p-6 bg-white border border-[#DCD3C7] text-center">
              <p className="text-sm text-[#7A7268] font-sans mb-4">{error}</p>
              <button
                onClick={() => loadRecommendations(true)}
                className="px-4 py-2 bg-[#181615] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors font-sans"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Recommendation Sections */}
          {!loading && !error && hasRecommendations && (
            <>
              <DiscoverSection
                title="Recommended for You"
                icon={<Star className="w-5 h-5" />}
                items={feed!.recommended_for_you}
                token={token}
                onImpression={handleImpression}
                accentColor="text-[#8C2524]"
              />

              <DiscoverSection
                title="Trending in Your Interests"
                icon={<TrendingUp className="w-5 h-5" />}
                items={feed!.trending_in_your_interests}
                token={token}
                onImpression={handleImpression}
                accentColor="text-amber-700"
              />

              <DiscoverSection
                title="Discover Something New"
                icon={<Compass className="w-5 h-5" />}
                items={feed!.discover_something_new}
                token={token}
                onImpression={handleImpression}
                accentColor="text-emerald-700"
              />

              {/* Fallback: show all recommendations if sections are empty */}
              {feed!.recommended_for_you.length === 0 &&
                feed!.trending_in_your_interests.length === 0 &&
                feed!.discover_something_new.length === 0 &&
                feed!.recommendations.length > 0 && (
                  <DiscoverSection
                    title="Stories For You"
                    icon={<BookOpen className="w-5 h-5" />}
                    items={feed!.recommendations}
                    token={token}
                    onImpression={handleImpression}
                  />
                )}
            </>
          )}

          {/* Empty State */}
          {!loading && !error && !hasRecommendations && <EmptyDiscoverState />}

          {/* Bottom CTA */}
          {!loading && hasRecommendations && (
            <div className="mt-4 mb-8 pt-8 border-t-2 border-[#181615] text-center">
              <p className="font-editorial-body italic text-sm text-[#6C645C] mb-4">
                Recommendations update as you read and explore
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center font-sans">
                <Link
                  href="/newspaper"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-[#181615] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors"
                >
                  <BookOpen className="w-4 h-4" />
                  Today&apos;s Edition
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <Link
                  href="/search"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-white border-2 border-[#181615] text-[#181615] text-xs font-bold uppercase tracking-wider hover:bg-[#F5EFEB] transition-colors"
                >
                  Search Articles
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      <Footer />

      {/* Modals */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={(newToken, newUser) => {
          localStorage.setItem("pn_auth_token", newToken);
          setToken(newToken);
          setUser(newUser);
          setShowAuthModal(false);
          loadRecommendations(true);
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
