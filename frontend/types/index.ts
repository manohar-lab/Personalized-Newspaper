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

