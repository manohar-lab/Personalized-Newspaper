export interface HealthResponse {
  status: string;
  service: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
  detail: string;
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
