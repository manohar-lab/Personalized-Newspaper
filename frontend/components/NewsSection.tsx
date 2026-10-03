"use client";

import React, { useState } from "react";
import { ThumbsUp, Bookmark, ExternalLink, EyeOff, BookOpen, Clock, Tag } from "lucide-react";
import { ArticlePreview } from "@/types";

const INITIAL_ARTICLES: ArticlePreview[] = [
  {
    id: "art-1",
    title: "AI Personalization Architecture: Building Next-Generation Content Engines",
    summary: "An exploration into how modern recommendation pipelines ingest RSS feeds, normalize HTML text, apply embeddings for category scoring, and rank stories for individual readers.",
    category: "Technology",
    source: "Tech Architecture Quarterly",
    publishedAt: "Today, 08:30 AM",
    readTimeMinutes: 5,
    relevanceScore: 98,
    isFullTextAvailable: true,
    originalUrl: "https://example.com/tech-architecture",
  },
  {
    id: "art-2",
    title: "The Renaissance of Digital Typography in Newspaper Design",
    summary: "Why leading editorial platforms are embracing classic serif mastheads, generous grid whitespace, and clean multi-column layouts to improve reader comprehension.",
    category: "Design",
    source: "Editorial Design Review",
    publishedAt: "Today, 07:15 AM",
    readTimeMinutes: 4,
    relevanceScore: 92,
    isFullTextAvailable: true,
    originalUrl: "https://example.com/editorial-design",
  },
  {
    id: "art-3",
    title: "Scraping & License Compliance: Respecting Publisher Rights",
    summary: "Understanding robots.txt, canonical syndication, and permitted scraping boundaries when aggregating multi-publisher news content.",
    category: "Engineering",
    source: "Web Standards Journal",
    publishedAt: "Yesterday",
    readTimeMinutes: 6,
    relevanceScore: 89,
    isFullTextAvailable: false,
    originalUrl: "https://example.com/web-standards",
  },
];

export function NewsSection() {
  const [likedArticles, setLikedArticles] = useState<Record<string, boolean>>({});
  const [savedArticles, setSavedArticles] = useState<Record<string, boolean>>({});
  const [hiddenArticles, setHiddenArticles] = useState<Record<string, boolean>>({});

  const toggleLike = (id: string) => {
    setLikedArticles((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleSave = (id: string) => {
    setSavedArticles((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const hideArticle = (id: string) => {
    setHiddenArticles((prev) => ({ ...prev, [id]: true }));
  };

  return (
    <section id="browse" className="my-10 max-w-7xl mx-auto px-4 sm:px-8">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end border-b-2 border-ink pb-3 mb-6 gap-2">
        <div>
          <span className="font-serif italic text-xs text-accent-red uppercase tracking-widest font-semibold">
            Phase 1 UI Shell Preview
          </span>
          <h3 className="font-serif text-2xl sm:text-3xl font-bold text-ink">
            Today's Front Page Layout
          </h3>
        </div>
        <div className="text-xs font-sans text-gray-500 italic">
          Articles will be dynamically ranked by AI classification in Phase 2
        </div>
      </div>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
        {/* Main Lead Story Column (8 cols) */}
        <div className="md:col-span-8 space-y-8">
          {INITIAL_ARTICLES.slice(0, 2).map((article, idx) => {
            if (hiddenArticles[article.id]) return null;

            return (
              <article
                key={article.id}
                className={`group pb-8 ${
                  idx === 0 ? "border-b border-paper-300" : ""
                }`}
              >
                <div className="flex items-center space-x-3 text-xs text-gray-600 mb-2 font-sans">
                  <span className="font-semibold text-accent-red flex items-center gap-1">
                    <Tag className="h-3 w-3" /> {article.category}
                  </span>
                  <span>•</span>
                  <span>{article.source}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" /> {article.readTimeMinutes} min read
                  </span>
                  <span className="ml-auto font-mono text-[11px] bg-paper-200 px-2 py-0.5 rounded text-ink font-semibold">
                    {article.relevanceScore}% Match
                  </span>
                </div>

                <h4 className="font-serif text-2xl sm:text-3xl font-bold text-ink group-hover:text-accent-red transition-colors leading-snug mb-3">
                  {article.title}
                </h4>

                <p className="font-sans text-sm sm:text-base text-gray-700 leading-relaxed mb-4">
                  {article.summary}
                </p>

                {/* Article Footer & Interactive Behavior Simulation */}
                <div className="flex flex-wrap items-center justify-between text-xs text-gray-600 gap-3 pt-2">
                  <div className="flex items-center space-x-4 font-sans">
                    <button
                      onClick={() => toggleLike(article.id)}
                      className={`flex items-center space-x-1.5 transition-colors px-2 py-1 rounded ${
                        likedArticles[article.id]
                          ? "text-accent-red bg-red-50 font-bold"
                          : "hover:text-ink"
                      }`}
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                      <span>{likedArticles[article.id] ? "Liked" : "Like"}</span>
                    </button>

                    <button
                      onClick={() => toggleSave(article.id)}
                      className={`flex items-center space-x-1.5 transition-colors px-2 py-1 rounded ${
                        savedArticles[article.id]
                          ? "text-ink bg-paper-200 font-bold"
                          : "hover:text-ink"
                      }`}
                    >
                      <Bookmark className="h-3.5 w-3.5" />
                      <span>{savedArticles[article.id] ? "Saved" : "Save"}</span>
                    </button>

                    <button
                      onClick={() => hideArticle(article.id)}
                      className="flex items-center space-x-1.5 hover:text-rose-700 transition-colors px-2 py-1 rounded"
                    >
                      <EyeOff className="h-3.5 w-3.5" />
                      <span>Not interested</span>
                    </button>
                  </div>

                  <div>
                    {article.isFullTextAvailable ? (
                      <span className="inline-flex items-center gap-1 font-semibold text-accent-red hover:underline cursor-pointer">
                        <BookOpen className="h-3.5 w-3.5" /> Read Full Article
                      </span>
                    ) : (
                      <a
                        href={article.originalUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 font-semibold text-gray-700 hover:text-ink hover:underline"
                      >
                        <ExternalLink className="h-3.5 w-3.5" /> Open Original Source
                      </a>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        {/* Sidebar News Desk Column (4 cols) */}
        <div className="md:col-span-4 border-l-0 md:border-l border-paper-300 pl-0 md:pl-6 space-y-6">
          <div className="bg-paper-100 p-4 border border-paper-300 rounded-sm">
            <h5 className="font-serif font-bold text-sm text-ink uppercase tracking-wider border-b border-paper-300 pb-2 mb-3">
              Personalization Radar
            </h5>
            <p className="font-sans text-xs text-gray-600 leading-relaxed mb-4">
              As you read stories, your personal interest profile dynamically adjusts interest vectors across categories.
            </p>
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-xs font-semibold mb-1">
                  <span>Technology & AI</span>
                  <span>95%</span>
                </div>
                <div className="w-full bg-paper-200 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-accent-red h-full w-[95%]"></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold mb-1">
                  <span>Architecture & System Design</span>
                  <span>88%</span>
                </div>
                <div className="w-full bg-paper-200 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-ink h-full w-[88%]"></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold mb-1">
                  <span>Web Scraping & Open Data</span>
                  <span>78%</span>
                </div>
                <div className="w-full bg-paper-200 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-gray-600 h-full w-[78%]"></div>
                </div>
              </div>
            </div>
          </div>

          {/* Secondary Story Card */}
          {INITIAL_ARTICLES.slice(2).map((article) => {
            if (hiddenArticles[article.id]) return null;
            return (
              <div key={article.id} className="border-b border-paper-300 pb-4">
                <span className="text-[11px] font-semibold text-accent-red uppercase tracking-wide">
                  {article.category}
                </span>
                <h5 className="font-serif font-bold text-base text-ink hover:text-accent-red transition-colors my-1">
                  {article.title}
                </h5>
                <p className="font-sans text-xs text-gray-600 line-clamp-3 mb-2">
                  {article.summary}
                </p>
                <div className="flex justify-between items-center text-[11px] text-gray-500">
                  <span>{article.source}</span>
                  <a
                    href={article.originalUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 font-semibold text-ink hover:underline"
                  >
                    Original <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
