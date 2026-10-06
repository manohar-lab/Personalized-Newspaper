"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { ArticleMetadata } from "@/components/ArticleMetadata";
import { ArticleCard } from "@/components/ArticleCard";
import { AuthModal } from "@/components/AuthModal";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Footer } from "@/components/Footer";
import {
  fetchArticleById,
  fetchCurrentUser,
  saveArticle,
  unsaveArticle,
  likeArticle,
  unlikeArticle,
  markArticleNotInterested,
  startReadingSession,
  heartbeatReadingSession,
  endReadingSession,
  fetchMoreLikeThis,
  recordRecommendationInteraction,
} from "@/lib/api";
import { ArticleDetail, User, RecommendationItem } from "@/types";
import {
  ArrowLeft,
  Bookmark,
  Heart,
  ThumbsDown,
  Share2,
  Check,
  Clock,
  BookOpen,
  ShieldAlert,
  Sparkles,
  Compass,
} from "lucide-react";

export default function ArticlePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const articleId = params?.id as string;
  const sourceContext = searchParams.get("source") || "DIRECT";

  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const [isSaved, setIsSaved] = useState<boolean>(false);
  const [isLiked, setIsLiked] = useState<boolean>(false);
  const [isNotInterested, setIsNotInterested] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [showInterestsModal, setShowInterestsModal] = useState<boolean>(false);

  // More Like This recommendations
  const [moreLikeThis, setMoreLikeThis] = useState<RecommendationItem[]>([]);
  const [moreLikeThisLoading, setMoreLikeThisLoading] = useState(false);

  // Reading Session & Engagement Tracking State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [scrollProgress, setScrollProgress] = useState<number>(0);
  const maxScrollRef = useRef<number>(0);
  const activeSecondsRef = useRef<number>(0);
  const isVisibleRef = useRef<boolean>(true);
  const sessionIdRef = useRef<string | null>(null);
  const articleIdRef = useRef<string>(articleId);
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    articleIdRef.current = articleId;
  }, [articleId]);

  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token");
    if (savedToken) {
      setToken(savedToken);
      tokenRef.current = savedToken;
      fetchCurrentUser(savedToken)
        .then(setUser)
        .catch(() => {});
    }
  }, []);

  useEffect(() => {
    if (!articleId) return;

    const loadArticle = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchArticleById(articleId, token || undefined);
        setArticle(data);
        setIsSaved(Boolean(data.is_saved));
        setIsLiked(Boolean(data.is_liked));
        setIsNotInterested(Boolean(data.is_not_interested));
      } catch (err: any) {
        setError(err?.message || "Failed to load article");
      } finally {
        setLoading(false);
      }
    };

    loadArticle();
  }, [articleId, token]);

  // Load "More like this" recommendations (separate from existing related_articles)
  useEffect(() => {
    if (!articleId) return;
    setMoreLikeThisLoading(true);
    fetchMoreLikeThis(articleId, token || undefined, 6)
      .then((res) => setMoreLikeThis(res.recommendations || []))
      .catch(() => setMoreLikeThis([]))
      .finally(() => setMoreLikeThisLoading(false));
  }, [articleId, token]);

  // Start Reading Session on Mount
  useEffect(() => {
    if (!articleId || !token) return;

    let isCancelled = false;
    startReadingSession(articleId, token, sourceContext)
      .then((res) => {
        if (!isCancelled && res.session_id) {
          setSessionId(res.session_id);
          sessionIdRef.current = res.session_id;
        }
      })
      .catch((err) => {
        console.warn("Failed to initiate reading session:", err);
      });

    return () => {
      isCancelled = true;
    };
  }, [articleId, token, sourceContext]);

  // Tab Visibility & Active Reading Measurement
  useEffect(() => {
    const handleVisibilityChange = () => {
      isVisibleRef.current = document.visibilityState === "visible";
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  // Active Reading Timer (only increments when tab is actively visible)
  useEffect(() => {
    const timer = setInterval(() => {
      if (isVisibleRef.current) {
        activeSecondsRef.current += 1;
      }
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Scroll Tracking
  useEffect(() => {
    const handleScroll = () => {
      const windowHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight - windowHeight;
      if (documentHeight <= 0) return;

      const currentScroll = Math.max(0, window.scrollY);
      const pct = Math.min(100, Math.round((currentScroll / documentHeight) * 100));

      setScrollProgress(pct);
      if (pct > maxScrollRef.current) {
        maxScrollRef.current = pct;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Heartbeat (every 15s when tab is visible and session active)
  useEffect(() => {
    if (!sessionId || !token) return;

    const interval = setInterval(() => {
      if (isVisibleRef.current && sessionIdRef.current && tokenRef.current) {
        heartbeatReadingSession(
          sessionIdRef.current,
          maxScrollRef.current,
          activeSecondsRef.current,
          tokenRef.current
        ).catch((err) => {
          console.warn("Reading heartbeat failed:", err);
        });
      }
    }, 15000);

    return () => clearInterval(interval);
  }, [sessionId, token]);

  // End Session on Component Unmount or Tab Close
  useEffect(() => {
    const endCurrentSession = () => {
      const currentSessionId = sessionIdRef.current;
      const currentArticleId = articleIdRef.current;
      const currentToken = tokenRef.current;

      if (currentSessionId && currentArticleId && currentToken) {
        endReadingSession(
          currentSessionId,
          currentArticleId,
          maxScrollRef.current,
          maxScrollRef.current,
          currentToken
        ).catch(() => {});
      }
    };

    const handleBeforeUnload = () => {
      endCurrentSession();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      endCurrentSession();
    };
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleSaveToggle = async () => {
    if (!token) {
      setShowAuthModal(true);
      return;
    }
    if (!article) return;

    try {
      if (isSaved) {
        await unsaveArticle(article.id, token);
        setIsSaved(false);
        showToast("Removed from your saved stories");
      } else {
        await saveArticle(article.id, token);
        setIsSaved(true);
        showToast("Saved to your reading list");
      }
    } catch {
      showToast("Error updating bookmark");
    }
  };

  const handleLikeToggle = async () => {
    if (!token) {
      setShowAuthModal(true);
      return;
    }
    if (!article) return;

    try {
      if (isLiked) {
        await unlikeArticle(article.id, token);
        setIsLiked(false);
        showToast("Like removed");
      } else {
        await likeArticle(article.id, token);
        setIsLiked(true);
        showToast("Story marked as liked");
      }
    } catch {
      showToast("Error liking story");
    }
  };

  const handleNotInterested = async () => {
    if (!token) {
      setShowAuthModal(true);
      return;
    }
    if (!article) return;

    try {
      await markArticleNotInterested(article.id, token);
      setIsNotInterested(true);
      showToast("Topic preference updated: marked as not interested");
    } catch {
      showToast("Error saving feedback");
    }
  };

  const handleShare = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      showToast("Article link copied to clipboard");
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-between bg-[#FAF8F5] text-[#181615]">
      {/* Subtle Top Reading Progress Indicator Bar */}
      <div className="fixed top-0 left-0 right-0 z-50 h-1.5 bg-[#E5DDD0]/50 backdrop-blur-sm pointer-events-none">
        <div
          className="h-full bg-[#8C2524] transition-all duration-150 ease-out shadow-sm"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

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

        {/* Toast Alert */}
        {toastMessage && (
          <div className="fixed bottom-6 right-6 z-50 bg-[#181615] text-[#FAF8F5] px-5 py-3 rounded-sm shadow-xl font-sans text-xs flex items-center gap-2 border border-[#4A453E] animate-bounce">
            <Check className="w-4 h-4 text-emerald-400" />
            <span>{toastMessage}</span>
          </div>
        )}

        <div className="max-w-4xl mx-auto px-4 sm:px-8 py-8">
          {/* Back to Newspaper Button & Reading Progress */}
          <div className="mb-6 flex items-center justify-between border-b border-[#E4DCCF] pb-3 font-sans">
            <Link
              href="/newspaper"
              className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#181615] hover:text-[#8C2524] transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Newspaper</span>
            </Link>

            <div className="flex items-center gap-4">
              {/* Subtle Scroll Reading Progress Indicator */}
              <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-[#7A7268]">
                <div className="w-24 h-1.5 bg-[#E5DDD0] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#8C2524] transition-all duration-200"
                    style={{ width: `${scrollProgress}%` }}
                  />
                </div>
                <span className="font-semibold text-[#181615]">{scrollProgress}%</span>
              </div>

              {article && (
                <span className="text-xs text-[#7A7268] font-mono">
                  {article.language.toUpperCase()} • {article.reading_time_minutes} MIN READ
                </span>
              )}
            </div>
          </div>

          {loading ? (
            <div className="space-y-6 animate-pulse py-8 font-sans">
              <div className="h-4 w-32 bg-[#E5DDD0] rounded" />
              <div className="h-12 w-full bg-[#DCD3C7] rounded" />
              <div className="h-6 w-3/4 bg-[#E5DDD0] rounded" />
              <div className="h-72 w-full bg-[#E5DDD0] rounded my-6" />
              <div className="space-y-3">
                <div className="h-4 w-full bg-[#E5DDD0] rounded" />
                <div className="h-4 w-5/6 bg-[#E5DDD0] rounded" />
                <div className="h-4 w-4/6 bg-[#E5DDD0] rounded" />
              </div>
            </div>
          ) : error || !article ? (
            <div className="p-8 text-center bg-white border border-[#DCD3C7] my-8 font-sans">
              <h2 className="text-xl font-bold text-[#181615] mb-2">Article Not Found</h2>
              <p className="text-sm text-[#7A7268] mb-6">
                {error || "The requested article is not available or is not in published status."}
              </p>
              <Link
                href="/newspaper"
                className="px-4 py-2 bg-[#181615] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors inline-flex items-center gap-2"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Return to Edition</span>
              </Link>
            </div>
          ) : (
            <article>
              {/* Ingestion / Demo Notice Banner */}
              {article.ingestion_method === "MANUAL" && (
                <div className="mb-6 p-3 bg-amber-50 border border-amber-300 rounded-sm flex items-start gap-2.5 text-xs text-amber-900 font-sans">
                  <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-semibold">Development / Demo Article:</strong> This is a sample editorial piece for testing the Personalized Newspaper reading experience and topic classification.
                  </div>
                </div>
              )}

              {/* Topics Tags */}
              <div className="flex flex-wrap gap-2 mb-3">
                {article.topics.map((t) => (
                  <span
                    key={t.slug}
                    className="px-2.5 py-0.5 bg-[#8C2524] text-white text-[11px] font-bold uppercase tracking-wider rounded-sm font-sans"
                  >
                    {t.name}
                  </span>
                ))}
              </div>

              {/* Article Headline */}
              <h1 className="font-editorial-heading font-black text-3xl sm:text-4xl lg:text-5xl text-[#110F0E] leading-[1.15] mb-4">
                {article.title}
              </h1>

              {/* Subtitle / Deck */}
              {article.description && (
                <p className="font-editorial-body italic text-lg sm:text-xl text-[#4E473F] leading-snug mb-6 pb-6 border-b border-[#E4DCCF]">
                  {article.description}
                </p>
              )}

              {/* Author & Byline Meta */}
              <div className="flex flex-wrap items-center justify-between gap-4 mb-8 text-xs font-sans text-[#6C645C]">
                <div>
                  {article.author && (
                    <div className="font-bold text-[#181615] text-sm">
                      By {article.author}
                    </div>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    {article.source_name && (
                      <span className="font-semibold text-[#8C2524]">{article.source_name}</span>
                    )}
                    <span>•</span>
                    <span>
                      {new Date(article.published_at).toLocaleDateString("en-US", {
                        weekday: "long",
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                      })}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      <span>{article.reading_time_minutes} min read</span>
                    </span>
                  </div>
                </div>

                {/* Quick actions top */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleLikeToggle}
                    className={`p-2 border rounded-sm transition-colors ${
                      isLiked ? "bg-rose-50 border-rose-300 text-rose-700" : "bg-white border-[#DCD3C7] text-[#5C554E] hover:bg-[#F5EFEB]"
                    }`}
                    title="Like story"
                  >
                    <Heart className={`w-4 h-4 ${isLiked ? "fill-rose-700" : ""}`} />
                  </button>
                  <button
                    onClick={handleSaveToggle}
                    className={`p-2 border rounded-sm transition-colors ${
                      isSaved ? "bg-red-50 border-red-300 text-[#8C2524]" : "bg-white border-[#DCD3C7] text-[#5C554E] hover:bg-[#F5EFEB]"
                    }`}
                    title="Save story"
                  >
                    <Bookmark className={`w-4 h-4 ${isSaved ? "fill-[#8C2524]" : ""}`} />
                  </button>
                  <button
                    onClick={handleShare}
                    className="p-2 bg-white border border-[#DCD3C7] rounded-sm text-[#5C554E] hover:bg-[#F5EFEB] transition-colors"
                    title="Share story"
                  >
                    <Share2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Hero Image */}
              {article.image_url && (
                <div className="mb-10 overflow-hidden bg-[#E8E1D5] rounded-sm aspect-[16/9] shadow-md">
                  <img
                    src={article.image_url}
                    alt={article.title}
                    className="w-full h-full object-cover"
                  />
                </div>
              )}

              {/* Article Content Section: Full Text Available vs Excerpt */}
              {article.is_full_text_available && article.content ? (
                <div className="editorial-prose max-w-none mb-12 dropcap">
                  <div
                    dangerouslySetInnerHTML={{
                      __html: article.content
                        .replace(/\n\n/g, "</p><p>")
                        .replace(/### (.*)/g, "<h3>$1</h3>")
                        .replace(/#### (.*)/g, "<h4>$1</h4>")
                        .replace(/> (.*)/g, "<blockquote>$1</blockquote>")
                        .replace(/```python([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
                        .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>"),
                    }}
                  />
                  {(article.canonical_url || article.source_url) && (
                    <div className="mt-8 pt-4 border-t border-[#E4DCCF] flex items-center justify-between text-xs text-[#7A7268] font-sans">
                      <span>Source: <strong className="text-[#181615]">{article.source_name || "Publisher"}</strong></span>
                      <a
                        href={article.canonical_url || article.source_url || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#8C2524] hover:underline inline-flex items-center gap-1 font-semibold"
                      >
                        <span>View original publication</span>
                        <span>↗</span>
                      </a>
                    </div>
                  )}
                </div>
              ) : (
                <div className="mb-12 space-y-6">
                  {article.extraction_status === "PAYWALL" && (
                    <div className="p-4 bg-amber-50/80 border border-amber-200/90 rounded-sm text-xs text-amber-900 font-sans flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-amber-700 shrink-0" />
                      <span>This publisher requires access on its website.</span>
                    </div>
                  )}

                  <div className="p-6 sm:p-8 bg-[#F5EFEB] border border-[#DCD3C7] rounded-sm">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-editorial-heading font-bold text-xl text-[#181615]">
                        Article Preview
                      </h3>
                      <span className="text-[11px] font-mono uppercase bg-[#E4DCCF] text-[#4A453E] px-2 py-0.5 rounded-sm">
                        Preview Mode
                      </span>
                    </div>

                    <p className="font-editorial-body text-base sm:text-lg text-[#3C3630] leading-relaxed mb-6">
                      {article.description || "No excerpt or full text available for this RSS discovery entry."}
                    </p>

                    <div className="pt-4 border-t border-[#E4DCCF] flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-sans">
                      <div className="text-xs text-[#7A7268]">
                        Discovered via {article.source_name || "publisher"} RSS feed.
                      </div>

                      {(article.canonical_url || article.source_url) && (
                        <a
                          href={article.canonical_url || article.source_url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-[#8C2524] text-white text-xs font-bold uppercase tracking-wider rounded-sm hover:bg-[#6E1C1B] transition-colors shadow-sm"
                        >
                          <span>Read original article</span>
                          <span className="text-sm">→</span>
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Sticky / Dedicated Action Bar */}
              <div className="bg-[#F5EFEB] border-2 border-[#181615] p-6 mb-16 flex flex-col sm:flex-row items-center justify-between gap-4 font-sans">
                <div>
                  <h4 className="font-bold text-sm text-[#181615] uppercase tracking-wide">
                    Did this article match your interests?
                  </h4>
                  <p className="text-xs text-[#6C645C] mt-0.5">
                    Your actions help the curation engine tune future editions.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={handleLikeToggle}
                    className={`px-4 py-2 border text-xs font-bold uppercase tracking-wider rounded-sm transition-colors flex items-center gap-1.5 ${
                      isLiked
                        ? "bg-rose-700 border-rose-700 text-white"
                        : "bg-white border-[#181615] text-[#181615] hover:bg-[#181615] hover:text-white"
                    }`}
                  >
                    <Heart className={`w-3.5 h-3.5 ${isLiked ? "fill-white" : ""}`} />
                    <span>{isLiked ? "Liked" : "Like Story"}</span>
                  </button>

                  <button
                    onClick={handleSaveToggle}
                    className={`px-4 py-2 border text-xs font-bold uppercase tracking-wider rounded-sm transition-colors flex items-center gap-1.5 ${
                      isSaved
                        ? "bg-[#8C2524] border-[#8C2524] text-white"
                        : "bg-white border-[#181615] text-[#181615] hover:bg-[#181615] hover:text-white"
                    }`}
                  >
                    <Bookmark className={`w-3.5 h-3.5 ${isSaved ? "fill-white" : ""}`} />
                    <span>{isSaved ? "Saved" : "Save for Later"}</span>
                  </button>

                  <button
                    onClick={handleNotInterested}
                    className={`px-4 py-2 border text-xs font-bold uppercase tracking-wider rounded-sm transition-colors flex items-center gap-1.5 ${
                      isNotInterested
                        ? "bg-gray-800 border-gray-800 text-white"
                        : "bg-white border-[#DCD3C7] text-[#7A7268] hover:border-gray-800 hover:text-gray-800"
                    }`}
                    title="Not interested in this type of story"
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                    <span>{isNotInterested ? "Marked Not Interested" : "Not Interested"}</span>
                  </button>
                </div>
              </div>

              {/* Related Articles Section */}
              {article.related_articles && article.related_articles.length > 0 && (
                <section className="border-t-2 border-[#181615] pt-8 mt-12">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="font-editorial-heading font-bold text-2xl text-[#181615]">
                      Related Stories
                    </h3>
                    <span className="text-xs text-[#7A7268] font-sans">
                      Articles sharing topics
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {article.related_articles.map((relArt) => (
                      <ArticleCard
                        key={relArt.id}
                        article={relArt}
                        token={token}
                        layout="standard"
                      />
                    ))}
                  </div>
                </section>
              )}

              {/* More Like This — AI-powered recommendations */}
              {moreLikeThis.length > 0 && (
                <section className="border-t border-[#DCD3C7] pt-8 mt-10">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-2">
                      <Compass className="w-5 h-5 text-[#8C2524]" />
                      <h3 className="font-editorial-heading font-bold text-xl text-[#181615]">
                        More Like This
                      </h3>
                    </div>
                    <span className="text-[11px] text-[#7A7268] font-mono uppercase tracking-wider font-sans">
                      Recommended
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {moreLikeThis.map((rec) => (
                      <Link
                        key={rec.article_id}
                        href={`/article/${rec.article_id}?source=RECOMMENDATION`}
                        onClick={() => {
                          if (token) {
                            recordRecommendationInteraction(rec.article_id, "CLICK", token, "ARTICLE").catch(() => {});
                          }
                        }}
                        className="group bg-white border border-[#E4DCCF] hover:border-[#181615] p-4 transition-all duration-200 hover:shadow-md"
                      >
                        {rec.image && (
                          <div className="aspect-[16/9] overflow-hidden bg-[#E8E1D5] mb-3 -mx-4 -mt-4">
                            <img src={rec.image} alt={rec.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                          </div>
                        )}
                        <p className="text-[10px] font-bold uppercase tracking-wider text-[#8C2524] mb-1.5 font-sans">
                          {rec.reason_text}
                        </p>
                        <h4 className="font-editorial-heading font-bold text-base text-[#110F0E] leading-snug mb-2 group-hover:text-[#8C2524] transition-colors line-clamp-2">
                          {rec.title}
                        </h4>
                        {rec.summary && (
                          <p className="font-editorial-body text-xs text-[#5C554E] line-clamp-2 leading-relaxed">
                            {rec.summary}
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-2 text-[10px] text-[#7A7268] font-sans">
                          {rec.source && <span className="font-semibold">{rec.source}</span>}
                          {rec.reading_time && (
                            <span className="flex items-center gap-0.5">
                              <Clock className="w-2.5 h-2.5" />
                              {rec.reading_time} min
                            </span>
                          )}
                        </div>
                      </Link>
                    ))}
                  </div>
                </section>
              )}
              {moreLikeThisLoading && (
                <div className="border-t border-[#DCD3C7] pt-8 mt-10 animate-pulse">
                  <div className="h-5 w-40 bg-[#E5DDD0] rounded mb-6" />
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <div key={i} className="bg-white border border-[#E4DCCF] p-4 space-y-3">
                        <div className="h-3 w-32 bg-[#E5DDD0] rounded" />
                        <div className="h-5 w-full bg-[#DCD3C7] rounded" />
                        <div className="h-3 w-3/4 bg-[#E5DDD0] rounded" />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </article>
          )}
        </div>
      </div>

      <Footer />

      {/* Auth Modal */}
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
