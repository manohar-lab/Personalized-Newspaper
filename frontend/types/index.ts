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
