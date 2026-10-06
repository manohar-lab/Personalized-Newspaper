"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { AuthModal } from "@/components/AuthModal";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Footer } from "@/components/Footer";
import {
  fetchCurrentUser,
  fetchMyReadingHistory,
  fetchMyContinueReading,
  clearMyReadingHistory,
  likeArticle,
  unlikeArticle,
  saveArticle,
  unsaveArticle,
} from "@/lib/api";
import {
  User,
  ReadingHistoryItem,
  ContinueReadingItem,
  EngagementLevel,
} from "@/types";
import {
  Clock,
  BookOpen,
  ArrowRight,
  Bookmark,
  Heart,
  Trash2,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Check,
  TrendingUp,
  History,
  CheckCircle2,
  Compass,
} from "lucide-react";

export default function ReadingHistoryPage() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const [historyItems, setHistoryItems] = useState<ReadingHistoryItem[]>([]);
  const [continueItems, setContinueItems] = useState<ContinueReadingItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [showInterestsModal, setShowInterestsModal] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isClearing, setIsClearing] = useState<boolean>(false);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
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
      const [histRes, contRes] = await Promise.all([
        fetchMyReadingHistory(token, page, 15),
        fetchMyContinueReading(token, 8),
      ]);
      setHistoryItems(histRes.items);
      setTotalPages(histRes.total_pages);
      setTotalCount(histRes.total);
      setContinueItems(contRes.items);
    } catch (err: any) {
      console.error("Failed to load reading history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadData();
    }
  }, [token, page]);

  const handleClearHistory = async () => {
    if (!token) return;
    if (!window.confirm("Are you sure you want to clear your entire reading history?")) {
      return;
    }

    setIsClearing(true);
    try {
      await clearMyReadingHistory(token);
      setHistoryItems([]);
      setContinueItems([]);
      setTotalCount(0);
      showToast("Reading history cleared successfully");
    } catch (err) {
      showToast("Failed to clear reading history");
    } finally {
      setIsClearing(false);
    }
  };

  const getEngagementBadge = (level: EngagementLevel) => {
    switch (level) {
      case "DEEP":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-300">
            <Sparkles className="w-3 h-3 text-emerald-600" />
            Deep Read
          </span>
        );
      case "HIGH":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-800 border border-blue-300">
            <TrendingUp className="w-3 h-3 text-blue-600" />
            High Read
          </span>
        );
      case "MEDIUM":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-300">
            Engaged
          </span>
        );
      case "LOW":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-stone-100 text-stone-700 border border-stone-300">
            Glanced
          </span>
        );
      case "BOUNCED":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-gray-100 text-gray-600 border border-gray-200">
            Bounced
          </span>
        );
    }
  };

  // Group history items by date
  const groupHistoryByDate = () => {
    const today = new Date().toISOString().split("T")[0];
    const yesterday = new Date(Date.now() - 86400000).toISOString().split("T")[0];

    const groups: { label: string; items: ReadingHistoryItem[] }[] = [
      { label: "TODAY", items: [] },
      { label: "YESTERDAY", items: [] },
      { label: "EARLIER", items: [] },
    ];

    historyItems.forEach((item) => {
      const itemDate = new Date(item.last_read_at).toISOString().split("T")[0];
      if (itemDate === today) {
        groups[0].items.push(item);
      } else if (itemDate === yesterday) {
        groups[1].items.push(item);
      } else {
        groups[2].items.push(item);
      }
    });

    return groups.filter((g) => g.items.length > 0);
  };

  const groupedHistory = groupHistoryByDate();

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

        <main className="max-w-5xl mx-auto px-4 sm:px-8 py-10 font-sans">
          {/* Header Section */}
          <div className="border-b-2 border-[#181615] pb-6 mb-8 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-[#8C2524] mb-1">
                <History className="w-4 h-4" />
                <span>Reading Ledger</span>
              </div>
              <h1 className="font-editorial-heading font-black text-4xl sm:text-5xl text-[#181615] tracking-tight">
                Reading History
              </h1>
              <p className="font-editorial-body italic text-base sm:text-lg text-[#5C554E] mt-1">
                Track your active reading habits, completion progress, and content engagement.
              </p>
            </div>

            {token && historyItems.length > 0 && (
              <button
                onClick={handleClearHistory}
                disabled={isClearing}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 rounded-sm transition-colors self-start sm:self-auto"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{isClearing ? "Clearing..." : "Clear History"}</span>
              </button>
            )}
          </div>

          {!token ? (
            /* Unauthorized Prompt */
            <div className="p-12 text-center bg-white border border-[#DCD3C7] rounded-sm my-12 shadow-sm">
              <BookOpen className="w-12 h-12 text-[#8C2524] mx-auto mb-4 stroke-1" />
              <h2 className="font-editorial-heading font-bold text-2xl text-[#181615] mb-2">
                Sign In to View Reading History
              </h2>
              <p className="font-editorial-body text-base text-[#6C645C] max-w-md mx-auto mb-6">
                Your reading history, scroll progress, and personalized engagement analytics are securely saved to your account.
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
              <div className="h-40 bg-[#E8E1D5]/60 rounded-sm" />
              <div className="space-y-4">
                <div className="h-6 w-32 bg-[#DCD3C7] rounded" />
                <div className="h-24 bg-white border border-[#E4DCCF] rounded-sm" />
                <div className="h-24 bg-white border border-[#E4DCCF] rounded-sm" />
                <div className="h-24 bg-white border border-[#E4DCCF] rounded-sm" />
              </div>
            </div>
          ) : (
            <div className="space-y-12">
              {/* Continue Reading Shelf */}
              {continueItems.length > 0 && (
                <section className="bg-white border-2 border-[#181615] p-6 rounded-sm shadow-sm">
                  <div className="flex items-center justify-between mb-4 border-b border-[#E4DCCF] pb-3">
                    <div className="flex items-center gap-2">
                      <Compass className="w-5 h-5 text-[#8C2524]" />
                      <h2 className="font-editorial-heading font-bold text-xl text-[#181615]">
                        Continue Reading
                      </h2>
                    </div>
                    <span className="text-xs font-mono text-[#7A7268]">
                      {continueItems.length} in progress
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {continueItems.map((c) => (
                      <Link
                        key={c.article_id}
                        href={`/article/${c.article.id}?source=CONTINUE`}
                        className="p-4 bg-[#FAF8F5] border border-[#DCD3C7] rounded-sm hover:border-[#181615] transition-all group flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-[#8C2524]">
                              {c.article.topics?.[0]?.name || "Article"}
                            </span>
                            <span className="text-xs font-mono font-bold text-[#181615]">
                              {Math.round(c.progress_percentage)}% Read
                            </span>
                          </div>

                          <h3 className="font-editorial-heading font-bold text-base text-[#181615] group-hover:text-[#8C2524] transition-colors line-clamp-2 mb-3">
                            {c.article.title}
                          </h3>
                        </div>

                        <div>
                          {/* Progress Bar */}
                          <div className="w-full h-1.5 bg-[#E5DDD0] rounded-full overflow-hidden mb-3">
                            <div
                              className="h-full bg-[#8C2524] transition-all duration-300"
                              style={{ width: `${Math.max(8, c.progress_percentage)}%` }}
                            />
                          </div>

                          <div className="flex items-center justify-between text-[11px] text-[#6C645C] font-mono">
                            <span>
                              {c.article.reading_time_minutes} min read • {Math.round(c.total_duration_seconds)}s spent
                            </span>
                            <span className="font-bold text-[#181615] inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                              <span>Resume</span>
                              <ArrowRight className="w-3 h-3" />
                            </span>
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                </section>
              )}

              {/* History Timeline */}
              {historyItems.length === 0 ? (
                <div className="p-12 text-center bg-white border border-[#DCD3C7] rounded-sm my-6">
                  <BookOpen className="w-10 h-10 text-[#7A7268] mx-auto mb-3 stroke-1" />
                  <h3 className="font-editorial-heading font-bold text-xl text-[#181615] mb-1">
                    No Reading History Yet
                  </h3>
                  <p className="font-editorial-body text-sm text-[#6C645C] mb-6">
                    Articles you explore from your daily newspaper or search will appear here.
                  </p>
                  <Link
                    href="/newspaper"
                    className="px-5 py-2.5 bg-[#181615] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors inline-flex items-center gap-2 rounded-sm"
                  >
                    <span>Explore Today&apos;s Edition</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              ) : (
                <div className="space-y-8">
                  {groupedHistory.map((group) => (
                    <section key={group.label} className="space-y-3">
                      <div className="border-b border-[#181615] pb-1">
                        <h2 className="font-mono text-xs font-bold text-[#181615] tracking-widest uppercase">
                          {group.label}
                        </h2>
                      </div>

                      <div className="divide-y divide-[#E4DCCF] bg-white border border-[#DCD3C7] rounded-sm shadow-sm">
                        {group.items.map((item) => (
                          <div
                            key={item.id}
                            className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-[#FDFBF7] transition-colors"
                          >
                            <div className="space-y-1.5 max-w-2xl">
                              <div className="flex flex-wrap items-center gap-2">
                                {item.article.topics?.slice(0, 2).map((t: any) => (
                                  <span
                                    key={t.slug || t}
                                    className="px-2 py-0.5 bg-[#F5EFEB] text-[#8C2524] text-[10px] font-bold uppercase tracking-wider rounded-sm"
                                  >
                                    {t.name || t}
                                  </span>
                                ))}
                                {getEngagementBadge(item.engagement_level)}
                              </div>

                              <Link
                                href={`/article/${item.article_id}?source=HISTORY`}
                                className="block font-editorial-heading font-bold text-lg text-[#181615] hover:text-[#8C2524] transition-colors"
                              >
                                {item.article.title}
                              </Link>

                              <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-[#7A7268] font-mono">
                                <span>{item.article.source_name || "Publisher"}</span>
                                <span>•</span>
                                <span>{item.article.reading_time_minutes} min read</span>
                                <span>•</span>
                                <span>Opened {item.open_count} {item.open_count === 1 ? "time" : "times"}</span>
                                {item.completion_count > 0 && (
                                  <>
                                    <span>•</span>
                                    <span className="text-emerald-700 font-semibold inline-flex items-center gap-1">
                                      <CheckCircle2 className="w-3 h-3" />
                                      <span>Completed</span>
                                    </span>
                                  </>
                                )}
                              </div>
                            </div>

                            {/* Progress & Duration Gauge */}
                            <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center shrink-0 border-t sm:border-t-0 pt-2 sm:pt-0 border-[#F5EFEB]">
                              <div className="text-right">
                                <span className="font-mono text-sm font-black text-[#181615]">
                                  Read {Math.round(item.last_completion_percentage || item.max_scroll_percentage)}%
                                </span>
                                <div className="w-24 h-1.5 bg-[#E5DDD0] rounded-full overflow-hidden mt-1">
                                  <div
                                    className="h-full bg-[#8C2524]"
                                    style={{
                                      width: `${Math.round(
                                        item.last_completion_percentage || item.max_scroll_percentage
                                      )}%`,
                                    }}
                                  />
                                </div>
                              </div>
                              <span className="text-[11px] font-mono text-[#7A7268] mt-1">
                                {Math.round(item.total_duration_seconds)}s spent
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between border-t border-[#E4DCCF] pt-4 font-mono text-xs">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="px-3 py-1.5 border border-[#DCD3C7] bg-white rounded-sm disabled:opacity-50 inline-flex items-center gap-1"
                      >
                        <ChevronLeft className="w-3.5 h-3.5" />
                        <span>Previous</span>
                      </button>
                      <span>
                        Page {page} of {totalPages}
                      </span>
                      <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="px-3 py-1.5 border border-[#DCD3C7] bg-white rounded-sm disabled:opacity-50 inline-flex items-center gap-1"
                      >
                        <span>Next</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      <Footer />

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
