import {
  HealthResponse,
  DatabaseHealthResponse,
  TokenResponse,
  User,
  Topic,
  UserInterest,
  Article,
  ArticleDetail,
  ArticleListResponse,
  NewspaperResponse,
  NewspaperEditionResponse,
  UserActionResponse,
  SavedArticlesListResponse,
  SearchFilters,
  SearchResponse,
  SearchSuggestionsResponse,
  SearchHistoryResponse,
  ReadingStartResponse,
  ReadingHeartbeatResponse,
  ReadingEndResponse,
  ReadingHistoryListResponse,
  ReadingHistoryItem,
  ContinueReadingListResponse,
  ReadingMetrics,
  SourceItem,
  SourceDetail,
  SourceListResponse,
  StoryCoverageResponse,
  ArticleCoverageItem,
  SourceReportRequest,
  ArticleReportRequest,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/?$/, "").replace(/\/+$/, "")
    : "http://localhost:8000");

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `HTTP request failed with status ${response.status}`
    );
  }

  return response.json();
}

// Health checks
export async function fetchBackendHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export async function fetchDatabaseHealth(): Promise<DatabaseHealthResponse> {
  return request<DatabaseHealthResponse>("/api/health/database");
}

// Authentication
export async function registerUser(
  email: string,
  password: string,
  full_name?: string
): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name }),
  });
}

export async function loginUser(
  email: string,
  password: string
): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchCurrentUser(token: string): Promise<User> {
  return request<User>("/api/auth/me", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Topics & Interests
export async function fetchTopics(): Promise<Topic[]> {
  return request<Topic[]>("/api/topics", { method: "GET" });
}

export async function fetchMyInterests(token: string): Promise<UserInterest[]> {
  return request<UserInterest[]>("/api/users/me/interests", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function submitOnboardingInterests(
  token: string,
  positive_topics: string[],
  negative_topics: string[]
): Promise<UserInterest[]> {
  return request<UserInterest[]>("/api/onboarding/interests", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ positive_topics, negative_topics }),
  });
}

export async function addOrUpdateInterest(
  token: string,
  topic_slug: string,
  interest_score: number,
  preference_type: "POSITIVE" | "NEGATIVE"
): Promise<UserInterest> {
  return request<UserInterest>("/api/users/me/interests", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ topic_slug, interest_score, preference_type }),
  });
}

export async function removeInterest(
  token: string,
  topic_slug: string
): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/users/me/interests/${topic_slug}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Personalized Newspaper API (Phase 9 Persistent Editions)
export async function fetchTodayEdition(
  token?: string
): Promise<NewspaperEditionResponse> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return request<NewspaperEditionResponse>("/api/newspaper/today", {
    method: "GET",
    headers,
  });
}

export async function regenerateTodayEdition(
  token: string,
  edition_date?: string
): Promise<NewspaperEditionResponse> {
  return request<NewspaperEditionResponse>("/api/newspaper/regenerate", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(edition_date ? { edition_date } : {}),
  });
}

export async function fetchEditionByDate(
  edition_date: string,
  token: string
): Promise<NewspaperEditionResponse> {
  return request<NewspaperEditionResponse>(`/api/newspaper/editions/${edition_date}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchPersonalizedNewspaper(
  token: string
): Promise<NewspaperEditionResponse> {
  return fetchTodayEdition(token);
}

// Articles API
export async function fetchArticles(
  params: { topic?: string; page?: number; limit?: number } = {},
  token?: string
): Promise<ArticleListResponse> {
  const query = new URLSearchParams();
  if (params.topic) query.set("topic", params.topic);
  if (params.page) query.set("page", params.page.toString());
  if (params.limit) query.set("limit", params.limit.toString());

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const qs = query.toString();
  return request<ArticleListResponse>(`/api/articles${qs ? `?${qs}` : ""}`, {
    method: "GET",
    headers,
  });
}

export async function fetchFeaturedArticle(token?: string): Promise<Article> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<Article>("/api/articles/featured", {
    method: "GET",
    headers,
  });
}

export async function fetchArticleById(
  id: string,
  token?: string
): Promise<ArticleDetail> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<ArticleDetail>(`/api/articles/${id}`, {
    method: "GET",
    headers,
  });
}

// User Actions: Save / Like / Not-Interested
export async function saveArticle(
  id: string,
  token: string
): Promise<UserActionResponse> {
  return request<UserActionResponse>(`/api/articles/${id}/save`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function unsaveArticle(
  id: string,
  token: string
): Promise<UserActionResponse> {
  return request<UserActionResponse>(`/api/articles/${id}/save`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function likeArticle(
  id: string,
  token: string
): Promise<UserActionResponse> {
  return request<UserActionResponse>(`/api/articles/${id}/like`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function unlikeArticle(
  id: string,
  token: string
): Promise<UserActionResponse> {
  return request<UserActionResponse>(`/api/articles/${id}/like`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function markArticleNotInterested(
  id: string,
  token: string
): Promise<UserActionResponse> {
  return request<UserActionResponse>(`/api/articles/${id}/not-interested`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchSavedArticles(
  token: string,
  page: number = 1,
  limit: number = 10
): Promise<SavedArticlesListResponse> {
  return request<SavedArticlesListResponse>(
    `/api/users/me/saved-articles?page=${page}&limit=${limit}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

// News Sources & Ingestion API
export async function fetchNewsSources(): Promise<any[]> {
  return request<any[]>("/api/news/sources", { method: "GET" });
}

export async function fetchNewsFeeds(): Promise<any[]> {
  return request<any[]>("/api/news/feeds", { method: "GET" });
}

export async function testFeed(feedId: string): Promise<any> {
  return request<any>(`/api/news/feeds/${feedId}/test`, { method: "POST" });
}

export async function triggerFeedIngestion(feedId: string, token: string): Promise<any> {
  return request<any>(`/api/news/feeds/${feedId}/ingest`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function triggerBatchIngestion(token: string): Promise<any> {
  return request<any>("/api/news/ingest", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// ----------------------------------------------------------------------------
// Phase 24 Intelligent Search & Discovery API
// ----------------------------------------------------------------------------
export async function searchArticles(
  filters: SearchFilters,
  token?: string
): Promise<SearchResponse> {
  const query = new URLSearchParams();
  if (filters.q !== undefined) query.set("q", filters.q);
  if (filters.topic) query.set("topic", filters.topic);
  if (filters.category) query.set("category", filters.category);
  if (filters.source) query.set("source", filters.source);
  if (filters.date_from) query.set("date_from", filters.date_from);
  if (filters.date_to) query.set("date_to", filters.date_to);
  if (filters.date_preset) query.set("date_preset", filters.date_preset);
  if (filters.article_type) query.set("article_type", filters.article_type);
  if (filters.language) query.set("language", filters.language);
  if (filters.page) query.set("page", filters.page.toString());
  if (filters.page_size) query.set("page_size", filters.page_size.toString());
  if (filters.sort_by) query.set("sort_by", filters.sort_by);
  if (filters.read_status) query.set("read_status", filters.read_status);
  if (filters.saved_status) query.set("saved_status", filters.saved_status);
  if (filters.result_type) query.set("result_type", filters.result_type);
  if (filters.deduplicate !== undefined) query.set("deduplicate", String(filters.deduplicate));

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const qs = query.toString();
  return request<SearchResponse>(`/api/search${qs ? `?${qs}` : ""}`, {
    method: "GET",
    headers,
  });
}

export async function fetchSearchSuggestions(
  query: string,
  limit: number = 8,
  token?: string
): Promise<SearchSuggestionsResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  return request<SearchSuggestionsResponse>(
    `/api/search/suggestions?q=${encodeURIComponent(query)}&limit=${limit}`,
    { method: "GET", headers }
  );
}

export async function fetchSearchFilters(): Promise<import("@/types").SearchFiltersMetaResponse> {
  return request<import("@/types").SearchFiltersMetaResponse>("/api/search/filters", {
    method: "GET",
  });
}

export async function fetchSearchHistory(
  token: string,
  limit: number = 20
): Promise<SearchHistoryResponse> {
  return request<SearchHistoryResponse>(
    `/api/search/recent?limit=${limit}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function clearSearchHistory(
  token: string
): Promise<{ success: boolean; deleted_count: number }> {
  return request<{ success: boolean; deleted_count: number }>(
    "/api/search/recent",
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

// ----------------------------------------------------------------------------
// Phase 12 Reading History & Session Tracking API
// ----------------------------------------------------------------------------
export async function startReadingSession(
  articleId: string,
  token?: string,
  sourceContext: string = "DIRECT"
): Promise<ReadingStartResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<ReadingStartResponse>("/api/reading/start", {
    method: "POST",
    headers,
    body: JSON.stringify({
      article_id: articleId,
      source_context: sourceContext,
    }),
  });
}

export async function heartbeatReadingSession(
  sessionId: string,
  scrollPercentage: number,
  activeDurationSeconds?: number,
  token?: string
): Promise<ReadingHeartbeatResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<ReadingHeartbeatResponse>("/api/reading/heartbeat", {
    method: "POST",
    headers,
    body: JSON.stringify({
      session_id: sessionId,
      scroll_percentage: scrollPercentage,
      active_duration_seconds: activeDurationSeconds,
    }),
  });
}

export async function endReadingSession(
  sessionId: string,
  articleId: string,
  completionPercentage?: number,
  maxScrollPercentage?: number,
  token?: string
): Promise<ReadingEndResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<ReadingEndResponse>("/api/reading/end", {
    method: "POST",
    headers,
    body: JSON.stringify({
      session_id: sessionId,
      article_id: articleId,
      completion_percentage: completionPercentage,
      max_scroll_percentage: maxScrollPercentage,
    }),
  });
}

export async function fetchMyReadingHistory(
  token: string,
  page: number = 1,
  pageSize: number = 20
): Promise<ReadingHistoryListResponse> {
  return request<ReadingHistoryListResponse>(
    `/api/users/me/reading-history?page=${page}&page_size=${pageSize}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function fetchMyContinueReading(
  token: string,
  limit: number = 10
): Promise<ContinueReadingListResponse> {
  return request<ContinueReadingListResponse>(
    `/api/users/me/continue-reading?limit=${limit}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function fetchArticleReadingState(
  articleId: string,
  token: string
): Promise<import("@/types").ArticleReadingState> {
  return request<import("@/types").ArticleReadingState>(
    `/api/articles/${articleId}/reading-state`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function startArticleReading(
  articleId: string,
  token: string,
  sourceContext: string = "DIRECT"
): Promise<ReadingStartResponse> {
  return request<ReadingStartResponse>(
    `/api/articles/${articleId}/reading/start?source_context=${encodeURIComponent(sourceContext)}`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function reportArticleReadingProgress(
  articleId: string,
  sessionId: string,
  scrollPercentage: number,
  activeDurationSeconds?: number,
  token?: string
): Promise<ReadingHeartbeatResponse> {
  const qp = new URLSearchParams({
    session_id: sessionId,
    scroll_percentage: String(scrollPercentage),
  });
  if (activeDurationSeconds !== undefined) {
    qp.append("active_duration_seconds", String(activeDurationSeconds));
  }
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<ReadingHeartbeatResponse>(
    `/api/articles/${articleId}/reading/progress?${qp.toString()}`,
    {
      method: "POST",
      headers,
    }
  );
}

export async function completeArticleReading(
  articleId: string,
  sessionId: string,
  completionPercentage?: number,
  maxScrollPercentage?: number,
  token?: string
): Promise<ReadingEndResponse> {
  const qp = new URLSearchParams({
    session_id: sessionId,
  });
  if (completionPercentage !== undefined) {
    qp.append("completion_percentage", String(completionPercentage));
  }
  if (maxScrollPercentage !== undefined) {
    qp.append("max_scroll_percentage", String(maxScrollPercentage));
  }
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<ReadingEndResponse>(
    `/api/articles/${articleId}/reading/complete?${qp.toString()}`,
    {
      method: "POST",
      headers,
    }
  );
}

export async function fetchArticleReadingHistory(
  articleId: string,
  token: string
): Promise<ReadingHistoryItem> {
  return request<ReadingHistoryItem>(
    `/api/articles/${articleId}/reading-history`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function clearMyReadingHistory(
  token: string
): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(
    "/api/users/me/reading-history",
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function fetchReadingMetrics(
  token?: string
): Promise<ReadingMetrics> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<ReadingMetrics>("/api/reading/metrics", {
    method: "GET",
    headers,
  });
}

// ----------------------------------------------------------------------------
// Phase 13: Dynamic User Interest Intelligence API
// ----------------------------------------------------------------------------
import {
  DynamicProfileResponse,
  ResetLearnedProfileResponse,
  RelevanceExplanationResponse,
} from "@/types";

export async function fetchDynamicInterestProfile(
  token?: string
): Promise<DynamicProfileResponse> {
  return request<DynamicProfileResponse>("/api/interests/dynamic-profile", {
    method: "GET",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

export async function updateTopicPreference(
  token: string,
  topicId: string,
  preference: "POSITIVE" | "NEGATIVE" | "NEUTRAL",
  strength: number = 1.0
): Promise<{ status: string; topic_id: string; preference: string; strength: number }> {
  return request<{ status: string; topic_id: string; preference: string; strength: number }>(
    "/api/interests/preferences",
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ topic_id: topicId, preference, strength }),
    }
  );
}

export async function removeLearnedInterest(
  token: string,
  topicId: string
): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(
    `/api/interests/learned/${topicId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function resetLearnedProfile(
  token: string
): Promise<ResetLearnedProfileResponse> {
  return request<ResetLearnedProfileResponse>("/api/interests/reset-learned", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchArticleRelevanceExplanation(
  token: string,
  articleId: string
): Promise<RelevanceExplanationResponse> {
  return request<RelevanceExplanationResponse>(
    `/api/interests/explanation/${articleId}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

// ----------------------------------------------------------------------------
// Phase 14: Personalized News Discovery & Recommendation Engine API
// ----------------------------------------------------------------------------
import {
  RecommendationFeedResponse,
  TrendingForYouResponse,
  MoreLikeThisResponse,
} from "@/types";

export async function fetchRecommendations(
  token?: string,
  limit: number = 20,
  page: number = 1,
  context: string = "DISCOVER",
  forceRefresh: boolean = false
): Promise<RecommendationFeedResponse> {
  const params = new URLSearchParams();
  params.set("limit", limit.toString());
  params.set("page", page.toString());
  params.set("context", context);
  if (forceRefresh) params.set("force_refresh", "true");

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<RecommendationFeedResponse>(
    `/api/recommendations?${params.toString()}`,
    { method: "GET", headers }
  );
}

export async function fetchTrendingForYou(
  token?: string,
  limit: number = 10
): Promise<TrendingForYouResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<TrendingForYouResponse>(
    `/api/recommendations/trending-for-you?limit=${limit}`,
    { method: "GET", headers }
  );
}

export async function fetchMoreLikeThis(
  articleId: string,
  token?: string,
  limit: number = 6
): Promise<MoreLikeThisResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<MoreLikeThisResponse>(
    `/api/articles/${articleId}/recommendations?limit=${limit}`,
    { method: "GET", headers }
  );
}

export async function recordRecommendationInteraction(
  articleId: string,
  interactionType: "IMPRESSION" | "CLICK",
  token?: string,
  context: string = "DISCOVER"
): Promise<{ status: string; article_id: string; interaction: string }> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<{ status: string; article_id: string; interaction: string }>(
    "/api/recommendations/interactions",
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        article_id: articleId,
        interaction_type: interactionType,
        context,
      }),
    }
  );
}

// ----------------------------------------------------------------------------
// Phase 15: Source Intelligence & Story Coverage API
// ----------------------------------------------------------------------------
export async function fetchSources(
  params: {
    search?: string;
    status?: string;
    following_only?: boolean;
    page?: number;
    limit?: number;
  } = {},
  token?: string
): Promise<SourceListResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const qp = new URLSearchParams();
  if (params.search) qp.append("search", params.search);
  if (params.status) qp.append("status", params.status);
  if (params.following_only) qp.append("following_only", "true");
  if (params.page) qp.append("page", String(params.page));
  if (params.limit) qp.append("limit", String(params.limit));

  const qs = qp.toString();
  return request<SourceListResponse>(`/api/news/sources${qs ? `?${qs}` : ""}`, {
    method: "GET",
    headers,
  });
}

export async function fetchSourceDetail(
  sourceId: string,
  token?: string
): Promise<SourceDetail> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<SourceDetail>(`/api/news/sources/${sourceId}`, {
    method: "GET",
    headers,
  });
}

export async function followSource(
  sourceId: string,
  token: string
): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(
    `/api/news/sources/${sourceId}/follow`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function unfollowSource(
  sourceId: string,
  token: string
): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(
    `/api/news/sources/${sourceId}/follow`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function muteSource(
  sourceId: string,
  token: string
): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(
    `/api/news/sources/${sourceId}/mute`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function unmuteSource(
  sourceId: string,
  token: string
): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>(
    `/api/news/sources/${sourceId}/mute`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function reportSource(
  sourceId: string,
  payload: SourceReportRequest,
  token?: string
): Promise<{ status: string; report_id: string; message: string }> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<{ status: string; report_id: string; message: string }>(
    `/api/news/sources/${sourceId}/report`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    }
  );
}

export async function reportArticle(
  articleId: string,
  reason: string,
  details?: string,
  token?: string
): Promise<{ status: string; report_id: string; message: string }> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const qp = new URLSearchParams();
  qp.append("reason", reason);
  if (details) qp.append("details", details);

  return request<{ status: string; report_id: string; message: string }>(
    `/api/articles/${articleId}/report?${qp.toString()}`,
    {
      method: "POST",
      headers,
    }
  );
}

export async function fetchStoryCoverage(
  articleId: string,
  token?: string
): Promise<StoryCoverageResponse> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<StoryCoverageResponse>(`/api/articles/${articleId}/coverage`, {
    method: "GET",
    headers,
  });
}

// ----------------------------------------------------------------------------
// Phase 16: Multi-Source Story Intelligence Engine API
// ----------------------------------------------------------------------------
import {
  StoryFeedResponse,
  StoryDetail,
  StoryTimelineItem,
  MultiSourceStoryCoverageResponse,
  StoryItem,
  StorySearchResponse,
} from "@/types";

export async function fetchStories(
  params?: {
    status?: string;
    topic?: string;
    page?: number;
    limit?: number;
  },
  token?: string
): Promise<StoryFeedResponse> {
  const qp = new URLSearchParams();
  if (params?.status) qp.set("status", params.status);
  if (params?.topic) qp.set("topic", params.topic);
  if (params?.page) qp.set("page", params.page.toString());
  if (params?.limit) qp.set("limit", params.limit.toString());

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<StoryFeedResponse>(`/api/stories?${qp.toString()}`, {
    method: "GET",
    headers,
  });
}

export async function fetchStoryDetail(
  slugOrId: string,
  token?: string
): Promise<StoryDetail> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<StoryDetail>(`/api/stories/${slugOrId}`, {
    method: "GET",
    headers,
  });
}

export async function fetchStoryTimeline(
  slugOrId: string
): Promise<StoryTimelineItem[]> {
  return request<StoryTimelineItem[]>(`/api/stories/${slugOrId}/timeline`, {
    method: "GET",
  });
}

export async function fetchStoryMultiSourceCoverage(
  slugOrId: string
): Promise<MultiSourceStoryCoverageResponse> {
  return request<MultiSourceStoryCoverageResponse>(`/api/stories/${slugOrId}/coverage`, {
    method: "GET",
  });
}

export async function fetchRelatedStories(
  slugOrId: string,
  limit: number = 5
): Promise<StoryItem[]> {
  return request<StoryItem[]>(`/api/stories/${slugOrId}/related?limit=${limit}`, {
    method: "GET",
  });
}

export async function searchStories(
  query: string,
  params?: { topic?: string; status?: string; limit?: number; offset?: number }
): Promise<StorySearchResponse> {
  const qp = new URLSearchParams();
  qp.set("q", query);
  if (params?.topic) qp.set("topic", params.topic);
  if (params?.status) qp.set("status", params.status);
  if (params?.limit) qp.set("limit", params.limit.toString());
  if (params?.offset) qp.set("offset", params.offset.toString());

  return request<StorySearchResponse>(`/api/stories/search?${qp.toString()}`, {
    method: "GET",
  });
}

// ==========================================
// Phase 18: Personal News Briefing & Sessions
// ==========================================

export async function fetchTodayBriefing(
  token?: string
): Promise<import("@/types").NewsBriefingResponse | null> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  try {
    return await request<import("@/types").NewsBriefingResponse>("/api/briefings/today", {
      method: "GET",
      headers,
    });
  } catch {
    return null;
  }
}

export async function fetchBriefingHistory(
  token: string,
  limit: number = 10
): Promise<any[]> {
  return request<any[]>(`/api/briefings/history?limit=${limit}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function generateBriefing(
  token: string,
  forceRefresh: boolean = false
): Promise<import("@/types").NewsBriefingResponse> {
  return request<import("@/types").NewsBriefingResponse>("/api/briefings/generate", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
}

export async function startNewsSession(token: string): Promise<{ session_id: string; started_at: string }> {
  return request<{ session_id: string; started_at: string }>("/api/news/sessions/start", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function sendSessionHeartbeat(
  token: string,
  sessionId: string,
  storiesDelta: number = 0,
  articlesDelta: number = 0,
  meaningful: boolean = false
): Promise<any> {
  return request<any>(`/api/news/sessions/${sessionId}/heartbeat`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      stories_viewed_delta: storiesDelta,
      articles_opened_delta: articlesDelta,
      has_meaningful_activity: meaningful,
    }),
  });
}

export async function endNewsSession(
  token: string,
  sessionId: string
): Promise<any> {
  return request<any>(`/api/news/sessions/${sessionId}/end`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// ----------------------------------------------------------------------------
// Phase 19: Advanced User Behavioral Learning Engine API
// ----------------------------------------------------------------------------
export async function fetchUserProfileInterests(token: string): Promise<any> {
  return request<any>("/api/profile/interests", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function overrideTopicPreference(
  token: string,
  topicId: string,
  overrideAction: string,
  strength: number = 1.0
): Promise<any> {
  return request<any>("/api/profile/interests/override", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      topic_id: topicId,
      override_action: overrideAction,
      strength,
    }),
  });
}

export async function rebuildUserProfile(token: string): Promise<any> {
  return request<any>("/api/profile/rebuild", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function recordBehaviorEvidence(
  token: string,
  evidence: {
    signal_type: string;
    target_type: string;
    target_id?: string;
    target_name?: string;
    dwell_time_seconds?: number;
    completion_ratio?: number;
    source_article_id?: string;
    source_story_id?: string;
    event_metadata?: any;
  }
): Promise<any> {
  return request<any>("/api/profile/evidence", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(evidence),
  });
}

// ----------------------------------------------------------------------------
// Phase 22: Automated Newsroom & Job Queue API
// ----------------------------------------------------------------------------
export async function fetchAdminJobs(
  params: { status?: string; job_type?: string; page?: number; limit?: number } = {},
  token: string
): Promise<any> {
  const qp = new URLSearchParams();
  if (params.status) qp.append("status", params.status);
  if (params.job_type) qp.append("job_type", params.job_type);
  if (params.page) qp.append("page", String(params.page));
  if (params.limit) qp.append("limit", String(params.limit));

  return request<any>(`/api/admin/jobs?${qp.toString()}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function retryAdminJob(jobId: string, token: string): Promise<any> {
  return request<any>(`/api/admin/jobs/${jobId}/retry`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchAdminSchedulerStatus(token: string): Promise<any> {
  return request<any>("/api/admin/scheduler/status", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchAdminEditions(
  page: number = 1,
  limit: number = 20,
  token: string
): Promise<any> {
  return request<any>(`/api/admin/editions?page=${page}&limit=${limit}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchUserNewspaperPreferences(token: string): Promise<any> {
  return request<any>("/api/users/newspaper-preferences", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function updateUserNewspaperPreferences(
  payload: any,
  token: string
): Promise<any> {
  return request<any>("/api/users/newspaper-preferences", {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

// ----------------------------------------------------------------------------
// Phase 23: Personalization Control Center & Transparency API
// ----------------------------------------------------------------------------
export async function fetchPersonalizationProfile(token: string): Promise<any> {
  return request<any>("/api/personalization/profile", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchPersonalizationSettings(token: string): Promise<any> {
  return request<any>("/api/personalization/settings", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function updatePersonalizationSettings(
  payload: any,
  token: string
): Promise<any> {
  return request<any>("/api/personalization/settings", {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

export async function fetchExplicitInterests(token: string): Promise<any> {
  return request<any>("/api/personalization/interests", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function addExplicitInterest(
  topicId: string,
  token: string
): Promise<any> {
  return request<any>("/api/personalization/interests", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ topic_id: topicId }),
  });
}

export async function deleteExplicitInterest(
  interestId: string,
  token: string
): Promise<any> {
  return request<any>(`/api/personalization/interests/${interestId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function searchTopicsHierarchy(
  query: string = "",
  token?: string
): Promise<any> {
  const qp = query ? `?q=${encodeURIComponent(query)}` : "";
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return request<any>(`/api/personalization/topics/search${qp}`, {
    method: "GET",
    headers,
  });
}

export async function followTopic(topicId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/topics/${topicId}/follow`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function muteTopic(topicId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/topics/${topicId}/mute`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function unmuteTopic(topicId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/topics/${topicId}/unmute`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function adjustTopicFeedback(
  topicId: string,
  action: string,
  token: string
): Promise<any> {
  return request<any>(`/api/personalization/topics/${topicId}/adjust`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ action }),
  });
}

export async function followEntity(entityId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/entities/${entityId}/follow`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function muteEntity(entityId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/entities/${entityId}/mute`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function seeLessEntity(entityId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/entities/${entityId}/less`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function preferSource(sourceId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/sources/${sourceId}/prefer`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function mutePersonalizationSource(sourceId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/sources/${sourceId}/mute`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function reduceSource(sourceId: string, token: string): Promise<any> {
  return request<any>(`/api/personalization/sources/${sourceId}/reduce`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function fetchWhyAmISeeingThis(
  articleId: string,
  token: string
): Promise<any> {
  return request<any>(`/api/personalization/explanation/${articleId}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function pausePersonalizationLearning(token: string): Promise<any> {
  return request<any>("/api/personalization/pause", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function resumePersonalizationLearning(token: string): Promise<any> {
  return request<any>("/api/personalization/resume", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function resetPersonalizationProfile(token: string): Promise<any> {
  return request<any>("/api/personalization/reset", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function rebuildPersonalizationProfile(token: string): Promise<any> {
  return request<any>("/api/personalization/rebuild", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function clearTemporaryInterests(token: string): Promise<any> {
  return request<any>("/api/personalization/clear-temporary", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}




