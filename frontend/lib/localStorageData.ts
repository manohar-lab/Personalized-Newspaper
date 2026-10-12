import {
  Article,
  SavedArticleItem,
  ReadingHistoryItem,
  ContinueReadingItem,
  EngagementLevel,
} from "@/types";

const SAVED_ARTICLES_KEY = "pn_saved_articles";
const READING_HISTORY_KEY = "pn_reading_history";
const LIKED_ARTICLES_KEY = "pn_liked_articles";
const DISLIKED_ARTICLES_KEY = "pn_disliked_articles";
const LOCAL_INTERESTS_KEY = "pn_local_interests";

// ─── Local Storage Helper ───────────────────────────────────────────────────

function safeGetItem<T>(key: string, defaultValue: T): T {
  if (typeof window === "undefined") return defaultValue;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : defaultValue;
  } catch (e) {
    console.warn(`Error reading ${key} from localStorage:`, e);
    return defaultValue;
  }
}

function safeSetItem<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.warn(`Error writing ${key} to localStorage:`, e);
  }
}

// ─── Saved Articles ─────────────────────────────────────────────────────────

export function getLocalSavedArticles(): SavedArticleItem[] {
  return safeGetItem<SavedArticleItem[]>(SAVED_ARTICLES_KEY, []);
}

export function saveLocalArticle(article: Article): SavedArticleItem[] {
  const current = getLocalSavedArticles();
  const exists = current.some((item) => item.article.id === article.id);
  if (exists) return current;

  const newItem: SavedArticleItem = {
    id: `local_save_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
    article: { ...article, is_saved: true },
    saved_at: new Date().toISOString(),
  };

  const updated = [newItem, ...current];
  safeSetItem(SAVED_ARTICLES_KEY, updated);
  return updated;
}

export function unsaveLocalArticle(articleId: string): SavedArticleItem[] {
  const current = getLocalSavedArticles();
  const updated = current.filter((item) => item.article.id !== articleId);
  safeSetItem(SAVED_ARTICLES_KEY, updated);
  return updated;
}

export function isLocalArticleSaved(articleId: string): boolean {
  const current = getLocalSavedArticles();
  return current.some((item) => item.article.id === articleId);
}

// ─── Liked & Disliked Articles ──────────────────────────────────────────────

export function getLocalLikedArticles(): string[] {
  return safeGetItem<string[]>(LIKED_ARTICLES_KEY, []);
}

export function toggleLocalLikeArticle(articleId: string): boolean {
  const current = getLocalLikedArticles();
  const idx = current.indexOf(articleId);
  let isNowLiked: boolean;
  let updated: string[];

  if (idx >= 0) {
    updated = current.filter((id) => id !== articleId);
    isNowLiked = false;
  } else {
    updated = [...current, articleId];
    isNowLiked = true;
  }

  safeSetItem(LIKED_ARTICLES_KEY, updated);
  return isNowLiked;
}

export function isLocalArticleLiked(articleId: string): boolean {
  const current = getLocalLikedArticles();
  return current.includes(articleId);
}

export function getLocalDislikedArticles(): string[] {
  return safeGetItem<string[]>(DISLIKED_ARTICLES_KEY, []);
}

export function markLocalArticleDisliked(articleId: string): void {
  const current = getLocalDislikedArticles();
  if (!current.includes(articleId)) {
    safeSetItem(DISLIKED_ARTICLES_KEY, [...current, articleId]);
  }
}

export function isLocalArticleDisliked(articleId: string): boolean {
  const current = getLocalDislikedArticles();
  return current.includes(articleId);
}

// ─── Reading History & Continue Reading ─────────────────────────────────────

function computeEngagementLevel(
  scrollPct: number,
  durationSec: number
): EngagementLevel {
  if (scrollPct >= 80 && durationSec >= 120) return "DEEP";
  if (scrollPct >= 60 || durationSec >= 60) return "HIGH";
  if (scrollPct >= 30 || durationSec >= 20) return "MEDIUM";
  return "LOW";
}

export function getLocalReadingHistory(): ReadingHistoryItem[] {
  return safeGetItem<ReadingHistoryItem[]>(READING_HISTORY_KEY, []);
}

export function recordLocalReading(
  article: Article,
  scrollPercentage: number = 0,
  durationSeconds: number = 0
): void {
  const current = getLocalReadingHistory();
  const now = new Date().toISOString();
  const existingIndex = current.findIndex(
    (item) => item.article_id === article.id
  );

  const finalScroll = Math.max(0, Math.min(100, Math.round(scrollPercentage)));
  const finalDuration = Math.max(0, Math.round(durationSeconds));

  if (existingIndex >= 0) {
    const existing = current[existingIndex];
    const maxScroll = Math.max(existing.max_scroll_percentage, finalScroll);
    const totalDuration = existing.total_duration_seconds + finalDuration;
    const openCount = existing.open_count + (finalDuration === 0 ? 1 : 0);

    const updatedItem: ReadingHistoryItem = {
      ...existing,
      article,
      last_opened_at: now,
      last_read_at: now,
      open_count: openCount,
      total_duration_seconds: totalDuration,
      max_scroll_percentage: maxScroll,
      last_completion_percentage: finalScroll,
      engagement_score: Math.min(100, Math.round((maxScroll + totalDuration / 2) / 2)),
      engagement_level: computeEngagementLevel(maxScroll, totalDuration),
    };

    const rest = current.filter((_, i) => i !== existingIndex);
    safeSetItem(READING_HISTORY_KEY, [updatedItem, ...rest]);
  } else {
    const newItem: ReadingHistoryItem = {
      id: `local_hist_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      article_id: article.id,
      article,
      first_opened_at: now,
      last_opened_at: now,
      last_read_at: now,
      open_count: 1,
      total_duration_seconds: finalDuration,
      max_scroll_percentage: finalScroll,
      average_scroll_percentage: finalScroll,
      completion_count: finalScroll >= 90 ? 1 : 0,
      last_completion_percentage: finalScroll,
      engagement_score: Math.min(100, Math.round((finalScroll + finalDuration / 2) / 2)),
      engagement_level: computeEngagementLevel(finalScroll, finalDuration),
    };

    safeSetItem(READING_HISTORY_KEY, [newItem, ...current].slice(0, 100));
  }
}

export function clearLocalReadingHistory(): void {
  safeSetItem(READING_HISTORY_KEY, []);
}

export function getLocalContinueReading(limit: number = 8): ContinueReadingItem[] {
  const history = getLocalReadingHistory();
  // Unfinished reads: between 5% and 90% scroll or read recently
  return history
    .filter((h) => h.max_scroll_percentage >= 5 && h.max_scroll_percentage < 90)
    .slice(0, limit)
    .map((h) => ({
      article_id: h.article_id,
      article: h.article,
      last_read_at: h.last_read_at,
      progress_percentage: h.max_scroll_percentage,
      max_scroll_percentage: h.max_scroll_percentage,
      total_duration_seconds: h.total_duration_seconds,
      engagement_level: h.engagement_level,
    }));
}

// ─── Local Interests ────────────────────────────────────────────────────────

export interface LocalInterest {
  topic_slug: string;
  topic_name: string;
  preference: "POSITIVE" | "NEGATIVE";
  weight: number;
}

export function getLocalInterests(): LocalInterest[] {
  return safeGetItem<LocalInterest[]>(LOCAL_INTERESTS_KEY, []);
}

export function saveLocalInterest(
  topicSlug: string,
  topicName: string,
  preference: "POSITIVE" | "NEGATIVE" = "POSITIVE",
  weight: number = 0.9
): LocalInterest[] {
  const current = getLocalInterests();
  const filtered = current.filter((i) => i.topic_slug !== topicSlug);
  const updated: LocalInterest[] = [
    ...filtered,
    { topic_slug: topicSlug, topic_name: topicName, preference, weight },
  ];
  safeSetItem(LOCAL_INTERESTS_KEY, updated);
  return updated;
}

export function removeLocalInterest(topicSlug: string): LocalInterest[] {
  const current = getLocalInterests();
  const updated = current.filter((i) => i.topic_slug !== topicSlug);
  safeSetItem(LOCAL_INTERESTS_KEY, updated);
  return updated;
}
