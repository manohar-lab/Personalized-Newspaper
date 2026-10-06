export interface HealthResponse {
  status: string;
  service: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
  detail: string;
}

export interface UserProfile {
  id: string;
  display_name?: string;
  bio?: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  profile?: UserProfile;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Topic {
  id: string;
  name: string;
  slug: string;
  description?: string;
  parent_topic_id?: string;
  created_at: string;
}

export interface TopicSummary {
  id: string;
  name: string;
  slug: string;
}

export interface UserInterest {
  id: string;
  topic_slug: string;
  topic_name: string;
  interest_score: number;
  preference_type: "POSITIVE" | "NEGATIVE";
  source: string;
  created_at: string;
  updated_at: string;
}

export interface ArticlePreview {
  id: string;
  title: string;
  summary: string;
  category: string;
  source: string;
  publishedAt: string;
  readTimeMinutes: number;
  relevanceScore: number;
  isFullTextAvailable: boolean;
  originalUrl: string;
}

export interface Article {
  id: string;
  title: string;
  slug: string;
  description?: string | null;
  content?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  canonical_url?: string | null;
  source_id?: string | null;
  feed_id?: string | null;
  ingestion_method?: "RSS" | "SCRAPER" | "API" | "MANUAL";
  author?: string | null;
  image_url?: string | null;
  published_at: string;
  created_at: string;
  reading_time_minutes: number;
  status: "DRAFT" | "PUBLISHED" | "ARCHIVED";
  language: string;
  is_full_text_available: boolean;
  extraction_status?: "NOT_ATTEMPTED" | "PENDING" | "SUCCESS" | "PARTIAL" | "FAILED" | "ROBOTS_BLOCKED" | "PAYWALL" | "ACCESS_DENIED" | "UNSUPPORTED" | string;
  extraction_method?: "TRAFILATURA" | "JSON_LD" | "OPENGRAPH" | "FALLBACK" | string | null;
  primary_category?: string | null;
  article_type?: string | null;
  summary?: string | null;
  importance_score?: number | null;
  topics: TopicSummary[];
  is_saved?: boolean;
  is_liked?: boolean;
  is_not_interested?: boolean;
  relevance_score?: number | null;
}

export interface ArticleDetail extends Article {
  related_articles: Article[];
}

export interface ArticleListResponse {
  items: Article[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface EditionInfo {
  date: string;
  title: string;
  subtitle?: string | null;
}

export interface UserSummary {
  id: string;
  name: string;
  email: string;
}

export interface NewspaperSection {
  topic: TopicSummary;
  total_articles: number;
  articles: Article[];
}

export interface NewspaperResponse {
  edition: EditionInfo;
  user: UserSummary;
  curation_summary: string;
  has_interests: boolean;
  featured_article: Article | null;
  sections: NewspaperSection[];
}

export interface UserActionResponse {
  success: boolean;
  action: string;
  article_id: string;
  message: string;
}

export interface SavedArticleItem {
  id: string;
  article: Article;
  saved_at: string;
}

export interface SavedArticlesListResponse {
  items: SavedArticleItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export type StoryLayoutType = "LEAD" | "FEATURE" | "STANDARD" | "COMPACT";

export interface NewspaperStoryResponse {
  id: string;
  article_id: string;
  title: string;
  original_headline: string;
  summary?: string | null;
  content?: string | null;
  url: string;
  top_image_url?: string | null;
  author?: string | null;
  source_name: string;
  published_at?: string | null;
  section: string;
  position: number;
  layout_type: StoryLayoutType;
  editorial_score: number;
  is_lead: boolean;
  personalization_reason?: string | null;
  primary_category?: string | null;
  topics: string[];
  reading_time_minutes: number;
  is_saved: boolean;
  is_liked: boolean;
  is_read: boolean;
}

export interface NewspaperSectionResponse {
  name: string;
  display_name: string;
  stories: NewspaperStoryResponse[];
  story_count: number;
}

export interface NewspaperEditionResponse {
  id: string;
  user_id: string;
  edition_date: string;
  title: string;
  subtitle?: string | null;
  status: string;
  generated_at: string;
  lead_story?: NewspaperStoryResponse | null;
  sections: NewspaperSectionResponse[];
  total_stories: number;
}

// ----------------------------------------------------------------------------
// Phase 11 Search Types
// ----------------------------------------------------------------------------
export interface SearchFilters {
  q?: string;
  topic?: string;
  category?: string;
  source?: string;
  date_from?: string;
  date_to?: string;
  date_preset?: "today" | "yesterday" | "last_7_days" | "last_30_days" | string;
  article_type?: string;
  language?: string;
  page?: number;
  page_size?: number;
}

export interface SearchResultItem {
  article_id: string;
  title: string;
  summary?: string | null;
  source_name?: string | null;
  published_at?: string | null;
  primary_category?: string | null;
  topics: string[];
  entities: string[];
  top_image_url?: string | null;
  reading_time_minutes: number;
  is_full_text_available: boolean;
  full_text_score: number;
  semantic_score: number;
  search_score: number;
  personal_relevance_score?: number | null;
  final_score: number;
  match_explanation?: string | null;
}

export interface ParsedQueryInfo {
  raw_query: string;
  clean_keywords: string;
  detected_topics: string[];
  detected_entities: string[];
  detected_sources: string[];
  date_range_detected?: string | null;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: SearchResultItem[];
  parsed_query?: ParsedQueryInfo | null;
  execution_time_ms: number;
}

export interface SearchSuggestionItem {
  text: string;
  type: "TOPIC" | "ENTITY" | "KEYWORD" | "RECENT" | string;
  subtitle?: string | null;
}

export interface SearchSuggestionsResponse {
  query: string;
  suggestions: SearchSuggestionItem[];
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  filters?: string | null;
  result_count: number;
  created_at: string;
}

export interface SearchHistoryResponse {
  history: SearchHistoryItem[];
}

// Phase 12: Reading History & Engagement Intelligence Types
export type EngagementLevel = "BOUNCED" | "LOW" | "MEDIUM" | "HIGH" | "DEEP";

export interface ReadingStartResponse {
  session_id: string;
  article_id: string;
  started_at: string;
  source_context?: string;
}

export interface ReadingHeartbeatResponse {
  session_id: string;
  is_active: boolean;
  total_session_duration: number;
  max_scroll_percentage: number;
  is_completed: boolean;
}

export interface ReadingEndResponse {
  session_id: string;
  article_id: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  completion_percentage: number;
  max_scroll_percentage: number;
  engagement_score: number;
  engagement_level: EngagementLevel;
  is_completed: boolean;
}

export interface ReadingHistoryItem {
  id: string;
  article_id: string;
  article: Article;
  first_opened_at: string;
  last_opened_at: string;
  last_read_at: string;
  open_count: number;
  total_duration_seconds: number;
  max_scroll_percentage: number;
  average_scroll_percentage: number;
  completion_count: number;
  last_completion_percentage: number;
  engagement_score: number;
  engagement_level: EngagementLevel;
}

export interface ReadingHistoryListResponse {
  items: ReadingHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ContinueReadingItem {
  article_id: string;
  article: Article;
  last_read_at: string;
  progress_percentage: number;
  max_scroll_percentage: number;
  total_duration_seconds: number;
  engagement_level: EngagementLevel;
}

export interface ContinueReadingListResponse {
  items: ContinueReadingItem[];
  total: number;
}

export interface ReadingMetrics {
  average_reading_duration_seconds: number;
  completion_rate_percentage: number;
  average_scroll_depth_percentage: number;
  bounce_rate_percentage: number;
  deep_read_rate_percentage: number;
  total_articles_completed: number;
  total_sessions_count: number;
  total_reading_history_count: number;
}

// ----------------------------------------------------------------------------
// Phase 13: Dynamic User Interest Intelligence Engine Types
// ----------------------------------------------------------------------------
export type InterestStateType = "STRONG" | "EMERGING" | "STABLE" | "DECLINING" | "DORMANT";

export interface DynamicInterestItem {
  topic_id: string;
  name: string;
  slug: string;
  score: number;
  confidence: number;
  interest_type: "EXPLICIT" | "LEARNED" | "INFERRED";
  state: InterestStateType;
  evidence_count: number;
  positive_count: number;
  negative_count: number;
  last_positive_at?: string | null;
  parent_topic_name?: string | null;
}

export interface TopicPreferenceItem {
  topic_id: string;
  name: string;
  slug: string;
  preference: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
  strength: number;
  confidence: number;
}

export interface EntityAffinityItem {
  entity_id: string;
  name: string;
  score: number;
  confidence: number;
  evidence_count: number;
}

export interface DynamicProfileResponse {
  user_id: string;
  explicit_interests: DynamicInterestItem[];
  strong_interests: DynamicInterestItem[];
  emerging_interests: DynamicInterestItem[];
  stable_interests: DynamicInterestItem[];
  declining_interests: DynamicInterestItem[];
  dormant_interests: DynamicInterestItem[];
  avoided_topics: TopicPreferenceItem[];
  top_entities: EntityAffinityItem[];
  summary: string;
}

export interface ResetLearnedProfileResponse {
  status: string;
  message: string;
  explicit_interests_preserved: number;
}

export interface RelevanceExplanationResponse {
  article_id: string;
  article_title: string;
  explanation: string;
  primary_factors: string[];
  match_score: number;
}

// ----------------------------------------------------------------------------
// Phase 14: Personalized News Discovery & Recommendation Engine Types
// ----------------------------------------------------------------------------
export interface RecommendationItem {
  article_id: string;
  title: string;
  summary?: string | null;
  source?: string | null;
  published_at?: string | null;
  image?: string | null;
  reading_time?: number | null;
  recommendation_score_hidden: number;
  reason_type: string;
  reason_text: string;
  section?: string | null;
  is_new: boolean;
  is_read: boolean;
}

export interface RecommendationFeedResponse {
  total: number;
  page: number;
  limit: number;
  context: string;
  recommendations: RecommendationItem[];
  recommended_for_you: RecommendationItem[];
  trending_in_your_interests: RecommendationItem[];
  discover_something_new: RecommendationItem[];
}

export interface TrendingForYouResponse {
  total: number;
  recommendations: RecommendationItem[];
}

export interface MoreLikeThisResponse {
  article_id: string;
  recommendations: RecommendationItem[];
}

export interface RecommendationInteractionRequest {
  article_id: string;
  interaction_type: "IMPRESSION" | "CLICK";
  context?: string;
}


