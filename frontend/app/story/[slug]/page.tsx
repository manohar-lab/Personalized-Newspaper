"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { Footer } from "@/components/Footer";
import {
  fetchStoryDetail,
  fetchRelatedStories,
  fetchCurrentUser,
  fetchArticleById,
  saveArticle,
  unsaveArticle,
  likeArticle,
  unlikeArticle,
  markArticleNotInterested,
  startArticleReading,
  reportArticleReadingProgress,
  completeArticleReading,
  fetchArticleReadingState,
} from "@/lib/api";
import { StoryDetail, StoryItem, ArticleDetail, User, ArticleReadingState } from "@/types";
import {
  ArrowLeft,
  Bookmark,
  Heart,
  ThumbsDown,
  Clock,
  BookOpen,
  Sparkles,
  Layers,
  Check,
  Globe,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  AlertCircle,
  TrendingUp,
} from "lucide-react";

export default function StoryPage() {
  const params = useParams();
  const router = useRouter();
  const slug = params?.slug as string;

  const [story, setStory] = useState<StoryDetail | null>(null);
  const [related, setRelated] = useState<StoryItem[]>([]);
  const [primaryArticle, setPrimaryArticle] = useState<ArticleDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  // Article Action states
  const [isSaved, setIsSaved] = useState<boolean>(false);
  const [isLiked, setIsLiked] = useState<boolean>(false);
  const [isNotInterested, setIsNotInterested] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Reading progress & session tracking
  const [readingProgress, setReadingProgress] = useState<number>(0);
  const [readingState, setReadingState] = useState<ArticleReadingState | null>(null);
  const [showResumeBanner, setShowResumeBanner] = useState<boolean>(false);
  const sessionIdRef = useRef<string | null>(null);
  const activeSecondsRef = useRef<number>(0);
  const maxScrollRef = useRef<number>(0);
  const isVisibleRef = useRef<boolean>(true);

  // Load User & Token
  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token") || localStorage.getItem("token");
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser(savedToken)
        .then(setUser)
        .catch(() => {});
    }
  }, []);

  // Fetch Story Detail & Related Stories
  useEffect(() => {
    if (!slug) return;
    const loadStory = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchStoryDetail(slug, token || undefined);
        setStory(data);

        // Fetch primary article if present
        if (data.primary_article?.article_id) {
          try {
            const artData = await fetchArticleById(data.primary_article.article_id, token || undefined);
            setPrimaryArticle(artData);
            setIsSaved(Boolean(artData.is_saved));
            setIsLiked(Boolean(artData.is_liked));
            setIsNotInterested(Boolean(artData.is_not_interested));

            // Check reading state for resume
            if (token) {
              fetchArticleReadingState(data.primary_article.article_id, token)
                .then((state) => {
                  setReadingState(state);
                  if (state.last_scroll_percentage > 15 && !state.is_completed) {
                    setShowResumeBanner(true);
                  }
                })
                .catch(() => {});
            }
          } catch {
            // Non-blocking if individual article fails
          }
        }

        const rel = await fetchRelatedStories(slug, 4);
        setRelated(rel);
      } catch (err: any) {
        setError(err?.message || "Failed to load story intelligence.");
      } finally {
        setLoading(false);
      }
    };
    loadStory();
  }, [slug, token]);

  // Track tab visibility to avoid counting background time
  useEffect(() => {
    const handleVisibilityChange = () => {
      isVisibleRef.current = document.visibilityState === "visible";
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  // Initialize Reading Session
  useEffect(() => {
    if (!primaryArticle?.id || !token) return;

    let timer: NodeJS.Timeout;
    let heartbeatTimer: NodeJS.Timeout;

    // Start session
    startArticleReading(primaryArticle.id, token, "STORY_PAGE")
      .then((res) => {
        sessionIdRef.current = res.session_id;
      })
      .catch(() => {});

    // Count active seconds
    timer = setInterval(() => {
      if (isVisibleRef.current) {
        activeSecondsRef.current += 1;
      }
    }, 1000);

    // Periodic heartbeat (every 15 seconds)
    heartbeatTimer = setInterval(() => {
      if (sessionIdRef.current && isVisibleRef.current && primaryArticle?.id) {
        reportArticleReadingProgress(
          primaryArticle.id,
          sessionIdRef.current,
          maxScrollRef.current,
          activeSecondsRef.current,
          token
        ).catch(() => {});
      }
    }, 15000);

    return () => {
      clearInterval(timer);
      clearInterval(heartbeatTimer);
      if (sessionIdRef.current && primaryArticle?.id) {
        completeArticleReading(
          primaryArticle.id,
          sessionIdRef.current,
          readingProgress,
          maxScrollRef.current,
          token
        ).catch(() => {});
      }
    };
  }, [primaryArticle?.id, token, readingProgress]);

  // Scroll depth tracking
  useEffect(() => {
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) return;

      const progress = Math.min(100, Math.max(0, Math.round((scrollTop / docHeight) * 100)));
      setReadingProgress(progress);
      if (progress > maxScrollRef.current) {
        maxScrollRef.current = progress;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Show Toast
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Actions
  const handleToggleSave = async () => {
    if (!primaryArticle?.id || !token) {
      showToast("Sign in to save stories");
      return;
    }
    try {
      if (isSaved) {
        await unsaveArticle(primaryArticle.id, token);
        setIsSaved(false);
        showToast("Removed from Saved");
      } else {
        await saveArticle(primaryArticle.id, token);
        setIsSaved(true);
        showToast("Saved");
      }
    } catch {
      showToast("Action failed");
    }
  };

  const handleToggleLike = async () => {
    if (!primaryArticle?.id || !token) {
      showToast("Sign in to like stories");
      return;
    }
    try {
      if (isLiked) {
        await unlikeArticle(primaryArticle.id, token);
        setIsLiked(false);
        showToast("Like removed");
      } else {
        await likeArticle(primaryArticle.id, token);
        setIsLiked(true);
        showToast("Liked");
      }
    } catch {
      showToast("Action failed");
    }
  };

  const handleNotInterested = async () => {
    if (!primaryArticle?.id || !token) {
      showToast("Sign in to customize preferences");
      return;
    }
    try {
      await markArticleNotInterested(primaryArticle.id, token);
      setIsNotInterested(true);
      showToast("Got it — we'll show fewer stories like this");
    } catch {
      showToast("Action failed");
    }
  };

  const handleResumeReading = () => {
    if (readingState?.last_scroll_percentage) {
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const targetScroll = (readingState.last_scroll_percentage / 100) * docHeight;
      window.scrollTo({ top: targetScroll, behavior: "smooth" });
      setShowResumeBanner(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FBF9F5] dark:bg-[#121110] text-[#181615] dark:text-[#E8E6E3]">
        <NewspaperHeader />
        <div className="max-w-4xl mx-auto px-4 py-16 animate-pulse">
          <div className="h-4 bg-stone-300 dark:bg-stone-700 w-32 mb-4 rounded"></div>
          <div className="h-10 bg-stone-300 dark:bg-stone-700 w-full mb-4 rounded"></div>
          <div className="h-6 bg-stone-200 dark:bg-stone-800 w-3/4 mb-8 rounded"></div>
          <div className="h-64 bg-stone-200 dark:bg-stone-800 w-full mb-8 rounded"></div>
          <div className="space-y-4">
            <div className="h-4 bg-stone-200 dark:bg-stone-800 w-full rounded"></div>
            <div className="h-4 bg-stone-200 dark:bg-stone-800 w-5/6 rounded"></div>
            <div className="h-4 bg-stone-200 dark:bg-stone-800 w-4/6 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !story) {
    return (
      <div className="min-h-screen bg-[#FBF9F5] dark:bg-[#121110] text-[#181615] dark:text-[#E8E6E3]">
        <NewspaperHeader />
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <AlertCircle className="w-12 h-12 mx-auto text-amber-600 mb-4" />
          <h1 className="font-serif text-3xl font-bold mb-3">Story Unavailable</h1>
          <p className="text-stone-600 dark:text-stone-400 mb-6">
            {error || "We couldn't retrieve this story at the moment."}
          </p>
          <Link
            href="/newspaper"
            className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#181615] text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] text-sm font-medium rounded hover:opacity-90 transition-opacity"
          >
            <ArrowLeft className="w-4 h-4" /> Return to Newspaper
          </Link>
        </div>
      </div>
    );
  }

  const extractionStatus = primaryArticle?.extraction_status || "SUCCESS";
  const isPaywalled = extractionStatus === "PAYWALL";
  const isRobotsBlocked = extractionStatus === "ROBOTS_BLOCKED";
  const isExtractionFailed = extractionStatus === "FAILED" || extractionStatus === "UNSUPPORTED";
  const readingTime = primaryArticle?.reading_time_minutes || 4;

  return (
    <div className="min-h-screen bg-[#FBF9F5] dark:bg-[#121110] text-[#181615] dark:text-[#E8E6E3] transition-colors">
      {/* Top subtle reading progress indicator */}
      <div className="fixed top-0 left-0 right-0 z-50 h-1 bg-stone-200 dark:bg-stone-800">
        <div
          className="h-full bg-stone-800 dark:bg-stone-200 transition-all duration-150"
          style={{ width: `${readingProgress}%` }}
        />
      </div>

      <NewspaperHeader />

      {/* Resume Reading Floating Banner */}
      {showResumeBanner && (
        <div className="bg-amber-50 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-800/50 py-2.5 px-4 text-center text-xs text-amber-900 dark:text-amber-200 flex items-center justify-center gap-3 animate-fadeIn">
          <span>You were previously reading this story ({readingState?.last_scroll_percentage}%).</span>
          <button
            onClick={handleResumeReading}
            className="font-bold underline hover:opacity-80"
          >
            Continue reading →
          </button>
          <button
            onClick={() => setShowResumeBanner(false)}
            className="ml-2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-200"
            aria-label="Dismiss resume prompt"
          >
            ✕
          </button>
        </div>
      )}

      {/* Breadcrumbs & Navigation */}
      <div className="max-w-4xl mx-auto px-4 pt-6 pb-2">
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-stone-500 dark:text-stone-400">
          <Link href="/newspaper" className="hover:underline">
            Personal Daily
          </Link>
          <ChevronRight className="w-3.5 h-3.5" />
          <span className="font-semibold uppercase tracking-wider text-stone-800 dark:text-stone-200">
            {story.primary_topic_name || "Top Stories"}
          </span>
          <ChevronRight className="w-3.5 h-3.5" />
          <span className="truncate max-w-[200px] text-stone-400">{story.title}</span>
        </nav>
      </div>

      {/* Main Story Container */}
      <main className="max-w-4xl mx-auto px-4 py-6">
        {/* Story Header */}
        <header className="mb-8 border-b border-stone-200 dark:border-stone-800 pb-8">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider bg-stone-900 text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] rounded">
              {story.primary_topic_name || "NEWS"}
            </span>
            {story.status === "DEVELOPING" && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 rounded-full animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400"></span>
                Developing Story
              </span>
            )}
            {story.status === "UPDATED" && (
              <span className="px-2.5 py-0.5 text-xs font-medium uppercase tracking-wider bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 rounded">
                Updated
              </span>
            )}
          </div>

          <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl font-bold leading-tight tracking-tight mb-4">
            {story.title}
          </h1>

          {story.summary && (
            <p className="font-serif text-lg sm:text-xl text-stone-700 dark:text-stone-300 leading-relaxed mb-6 font-normal">
              {story.summary}
            </p>
          )}

          {/* Metadata Row */}
          <div className="flex flex-wrap items-center justify-between gap-4 text-xs sm:text-sm text-stone-500 dark:text-stone-400 border-t border-stone-200 dark:border-stone-800 pt-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                Updated {new Date(story.last_updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Layers className="w-4 h-4" />
                Covered by {story.source_count} {story.source_count === 1 ? "source" : "sources"}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <BookOpen className="w-4 h-4" />
                {readingTime} min read
              </span>
            </div>

            {/* Reading progress badge */}
            <div className="text-xs font-mono font-medium text-stone-500">
              ──────── {readingProgress}%
            </div>
          </div>

          {/* Personal Relevance Explanation Banner */}
          {story.personal_relevance_reason && (
            <div className="mt-4 p-3 bg-stone-100 dark:bg-stone-900/80 border-l-2 border-stone-800 dark:border-stone-200 text-xs text-stone-700 dark:text-stone-300 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-stone-600 dark:text-stone-400 shrink-0" />
              <span>{story.personal_relevance_reason}</span>
            </div>
          )}

          {/* What Changed Banner */}
          {story.what_changed && (
            <div className="mt-3 p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/40 rounded text-xs text-emerald-900 dark:text-emerald-200">
              <div className="font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5" /> What Changed
              </div>
              <p className="leading-relaxed">{story.what_changed}</p>
            </div>
          )}
        </header>

        {/* Action Toolbar */}
        <div className="flex items-center justify-between border-y border-stone-200 dark:border-stone-800 py-3 mb-8 text-xs font-medium">
          <div className="flex items-center gap-4">
            <button
              onClick={handleToggleLike}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition-colors ${
                isLiked
                  ? "bg-rose-50 dark:bg-rose-950 text-rose-600 dark:text-rose-400 font-bold"
                  : "hover:bg-stone-100 dark:hover:bg-stone-800 text-stone-700 dark:text-stone-300"
              }`}
              aria-label="Like story"
            >
              <Heart className={`w-4 h-4 ${isLiked ? "fill-rose-500 text-rose-500" : ""}`} />
              {isLiked ? "Liked" : "Like"}
            </button>

            <button
              onClick={handleToggleSave}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition-colors ${
                isSaved
                  ? "bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-400 font-bold"
                  : "hover:bg-stone-100 dark:hover:bg-stone-800 text-stone-700 dark:text-stone-300"
              }`}
              aria-label="Save story"
            >
              <Bookmark className={`w-4 h-4 ${isSaved ? "fill-amber-600 text-amber-600" : ""}`} />
              {isSaved ? "Saved" : "Save"}
            </button>

            <button
              onClick={handleNotInterested}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded transition-colors ${
                isNotInterested
                  ? "bg-stone-200 dark:bg-stone-700 text-stone-500"
                  : "hover:bg-stone-100 dark:hover:bg-stone-800 text-stone-500 hover:text-stone-800 dark:hover:text-stone-200"
              }`}
              aria-label="Mark not interested"
            >
              <ThumbsDown className="w-4 h-4" />
              {isNotInterested ? "Got it" : "Not interested"}
            </button>
          </div>

          {primaryArticle?.source_url && (
            <a
              href={primaryArticle.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-stone-600 dark:text-stone-400 hover:underline"
            >
              Original Source <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>

        {/* Hero Image if Available */}
        {primaryArticle?.image_url && (
          <figure className="mb-8">
            <img
              src={primaryArticle.image_url}
              alt={story.title}
              loading="lazy"
              className="w-full max-h-[480px] object-cover rounded border border-stone-200 dark:border-stone-800"
            />
            {primaryArticle.author && (
              <figcaption className="text-xs text-stone-500 dark:text-stone-400 mt-2 text-right">
                Photo via {primaryArticle.source_name || "Publisher"}
              </figcaption>
            )}
          </figure>
        )}

        {/* Editorial Body / Reader */}
        <section className="article-content max-w-2xl mx-auto font-serif text-lg leading-relaxed text-stone-800 dark:text-stone-200 mb-12">
          {isPaywalled ? (
            <div className="p-6 bg-stone-100 dark:bg-stone-900 border border-stone-300 dark:border-stone-700 rounded-lg text-center my-8">
              <ShieldAlert className="w-8 h-8 mx-auto text-amber-600 mb-3" />
              <h3 className="font-serif text-xl font-bold mb-2">Publisher Paywall</h3>
              <p className="text-stone-600 dark:text-stone-400 text-sm mb-4 font-sans leading-normal">
                Full article content is behind a subscription paywall at the original publisher.
              </p>
              {primaryArticle?.description && (
                <div className="italic text-stone-700 dark:text-stone-300 text-base mb-6 px-4 border-l-2 border-amber-500 text-left font-serif">
                  "{primaryArticle.description}"
                </div>
              )}
              {primaryArticle?.source_url && (
                <a
                  href={primaryArticle.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#181615] text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] font-sans text-sm font-semibold rounded hover:opacity-90 transition-opacity"
                >
                  Continue reading at {primaryArticle.source_name || "publisher"} →
                </a>
              )}
            </div>
          ) : isRobotsBlocked ? (
            <div className="p-6 bg-stone-100 dark:bg-stone-900 border border-stone-300 dark:border-stone-700 rounded-lg text-center my-8">
              <Globe className="w-8 h-8 mx-auto text-stone-500 mb-3" />
              <h3 className="font-serif text-xl font-bold mb-2">Content Not Available Here</h3>
              <p className="text-stone-600 dark:text-stone-400 text-sm mb-4 font-sans leading-normal">
                Full article content isn't available here in compliance with the publisher's robots policy.
              </p>
              {primaryArticle?.source_url && (
                <a
                  href={primaryArticle.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#181615] text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] font-sans text-sm font-semibold rounded hover:opacity-90"
                >
                  Read at original source →
                </a>
              )}
            </div>
          ) : isExtractionFailed || !primaryArticle?.content ? (
            <div className="p-6 bg-stone-100 dark:bg-stone-900 border border-stone-300 dark:border-stone-700 rounded-lg text-center my-8">
              <h3 className="font-serif text-xl font-bold mb-2">Full Text Unavailable</h3>
              <p className="text-stone-600 dark:text-stone-400 text-sm mb-4 font-sans leading-normal">
                We couldn't retrieve the full article content. Read it at the original source.
              </p>
              {primaryArticle?.source_url && (
                <a
                  href={primaryArticle.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#181615] text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] font-sans text-sm font-semibold rounded hover:opacity-90"
                >
                  Read original article →
                </a>
              )}
            </div>
          ) : (
            <div className="space-y-6">
              {primaryArticle.content.split("\n\n").map((para, idx) => (
                <p key={idx} className={idx === 0 ? "first-letter:font-serif first-letter:text-5xl first-letter:font-bold first-letter:float-left first-letter:mr-3 first-letter:leading-none text-stone-900 dark:text-stone-100" : ""}>
                  {para.trim()}
                </p>
              ))}
            </div>
          )}

          {/* Source Attribution Box */}
          <div className="mt-12 pt-6 border-t border-stone-300 dark:border-stone-700 font-sans text-xs text-stone-500 dark:text-stone-400 space-y-1">
            {primaryArticle?.source_name && (
              <div>
                <strong>Source:</strong> {primaryArticle.source_name}
              </div>
            )}
            {primaryArticle?.author && (
              <div>
                <strong>Author:</strong> {primaryArticle.author}
              </div>
            )}
            {primaryArticle?.published_at && (
              <div>
                <strong>Published:</strong> {new Date(primaryArticle.published_at).toLocaleString()}
              </div>
            )}
            {primaryArticle?.source_url && (
              <div className="pt-2">
                <a
                  href={primaryArticle.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-stone-800 dark:text-stone-200 font-semibold underline hover:opacity-80"
                >
                  Read original article →
                </a>
              </div>
            )}
          </div>
        </section>

        {/* Story Timeline Section */}
        {story.timeline && story.timeline.length > 0 && (
          <section className="mb-12 border-t border-stone-200 dark:border-stone-800 pt-8 max-w-2xl mx-auto">
            <h2 className="font-serif text-2xl font-bold mb-6 flex items-center gap-2">
              <Clock className="w-5 h-5 text-stone-700 dark:text-stone-300" /> Story Timeline
            </h2>
            <div className="relative border-l-2 border-stone-300 dark:border-stone-700 ml-3 space-y-6 pl-6">
              {story.timeline.map((item, idx) => (
                <div key={item.id || idx} className="relative group">
                  <div className="absolute -left-[31px] top-1.5 w-3 h-3 rounded-full bg-stone-900 dark:bg-stone-100 ring-4 ring-[#FBF9F5] dark:ring-[#121110]" />
                  <div className="text-xs font-mono font-semibold text-stone-500 dark:text-stone-400 mb-1">
                    {new Date(item.published_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • {new Date(item.published_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                  </div>
                  <h4 className="font-serif text-base font-bold text-stone-900 dark:text-stone-100 group-hover:underline">
                    {item.title}
                  </h4>
                  {item.snippet && (
                    <p className="text-xs text-stone-600 dark:text-stone-400 mt-1 leading-normal">
                      {item.snippet}
                    </p>
                  )}
                  <div className="text-[11px] text-stone-400 mt-1 font-sans">
                    {item.source_name || "News Source"}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Multi-Source Coverage */}
        {story.articles && story.articles.length > 1 && (
          <section className="mb-12 border-t border-stone-200 dark:border-stone-800 pt-8 max-w-2xl mx-auto">
            <h2 className="font-serif text-2xl font-bold mb-2 flex items-center gap-2">
              <Layers className="w-5 h-5 text-stone-700 dark:text-stone-300" /> Multi-Source Coverage
            </h2>
            <p className="text-xs text-stone-500 mb-6 font-sans">
              Covered by {story.source_count} {story.source_count === 1 ? "source" : "sources"}
            </p>
            <div className="space-y-4">
              {story.articles.map((art) => (
                <div
                  key={art.id}
                  className="p-4 bg-stone-50 dark:bg-stone-900/60 border border-stone-200 dark:border-stone-800 rounded flex flex-col sm:flex-row justify-between sm:items-center gap-3"
                >
                  <div>
                    <div className="text-[11px] font-bold uppercase tracking-wider text-stone-500 mb-1">
                      {art.source_name || "Publisher"} • {art.reading_time_minutes} min read
                    </div>
                    <h4 className="font-serif font-bold text-sm sm:text-base text-stone-900 dark:text-stone-100">
                      {art.title}
                    </h4>
                  </div>
                  {art.url && (
                    <a
                      href={art.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 text-xs font-semibold underline text-stone-700 dark:text-stone-300 hover:opacity-80"
                    >
                      Read source →
                    </a>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* You May Also Want to Read (Related Stories) */}
        {related && related.length > 0 && (
          <section className="border-t border-stone-200 dark:border-stone-800 pt-8 mt-12">
            <h2 className="font-serif text-2xl font-bold mb-6">You May Also Want to Read</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {related.map((rel) => (
                <Link
                  key={rel.id}
                  href={`/story/${rel.slug}`}
                  className="group block p-4 bg-stone-50 dark:bg-stone-900/50 border border-stone-200 dark:border-stone-800 rounded hover:border-stone-400 dark:hover:border-stone-600 transition-colors"
                >
                  <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-1 block">
                    {rel.primary_topic_name || "NEWS"}
                  </span>
                  <h3 className="font-serif font-bold text-base text-stone-900 dark:text-stone-100 group-hover:underline mb-2 line-clamp-2">
                    {rel.title}
                  </h3>
                  {rel.summary && (
                    <p className="text-xs text-stone-600 dark:text-stone-400 line-clamp-2 leading-relaxed">
                      {rel.summary}
                    </p>
                  )}
                  <div className="text-[11px] text-stone-400 mt-3 flex items-center justify-between">
                    <span>{rel.source_count} {rel.source_count === 1 ? "source" : "sources"}</span>
                    <span>{new Date(rel.last_updated_at).toLocaleDateString()}</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 right-6 z-50 bg-[#181615] text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] px-4 py-2.5 rounded shadow-lg text-xs font-medium flex items-center gap-2 animate-slideUp"
        >
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      <Footer />
    </div>
  );
}
