"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { fetchStoryDetail, fetchRelatedStories, fetchCurrentUser } from "@/lib/api";
import { StoryDetail, StoryItem, User } from "@/types";

export default function StoryDetailPage() {
  const params = useParams();
  const slug = params?.slug as string;

  const [story, setStory] = useState<StoryDetail | null>(null);
  const [related, setRelated] = useState<StoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activePerspective, setActivePerspective] = useState<string>("ALL");
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const t = localStorage.getItem("token");
    setToken(t);
    if (t) {
      fetchCurrentUser(t)
        .then(setUser)
        .catch(() => setUser(null));
    }
  }, []);

  useEffect(() => {
    if (!slug) return;
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchStoryDetail(slug, token || undefined);
        setStory(data);
        const rel = await fetchRelatedStories(slug, 4);
        setRelated(rel);
      } catch (err: any) {
        setError(err.message || "Failed to load story intelligence.");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [slug, token]);

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "DEVELOPING":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-700 border border-emerald-500/20 rounded-full animate-pulse">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            Developing Story
          </span>
        );
      case "ACTIVE":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold uppercase tracking-wider bg-blue-500/10 text-blue-700 border border-blue-500/20 rounded-full">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            Active
          </span>
        );
      case "STABLE":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium uppercase tracking-wider bg-amber-500/10 text-amber-700 border border-amber-500/20 rounded-full">
            Stable
          </span>
        );
      case "RESOLVED":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium uppercase tracking-wider bg-purple-500/10 text-purple-700 border border-purple-500/20 rounded-full">
            Resolved
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium uppercase tracking-wider bg-stone-500/10 text-stone-700 border border-stone-500/20 rounded-full">
            Archived
          </span>
        );
    }
  };

  const getRelationshipBadge = (rel: string) => {
    switch (rel.toUpperCase()) {
      case "PRIMARY":
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-[#181615] text-[#FBF9F5] rounded">
            Initial Report
          </span>
        );
      case "UPDATE":
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-emerald-700 text-white rounded">
            Latest Update
          </span>
        );
      case "ANALYSIS":
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-purple-700 text-white rounded">
            Analysis
          </span>
        );
      case "REACTION":
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-blue-700 text-white rounded">
            Reaction
          </span>
        );
      case "BACKGROUND":
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-amber-700 text-white rounded">
            Background
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider bg-[#ECE5DA] text-[#6C645C] rounded">
            Related
          </span>
        );
    }
  };

  const formatTimestamp = (dateStr?: string | null) => {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FBF9F5] font-serif">
        <NewspaperHeader user={user} />
        <main className="max-w-5xl mx-auto px-4 py-16 space-y-8 animate-pulse">
          <div className="h-6 bg-[#ECE5DA] rounded w-1/4"></div>
          <div className="h-12 bg-[#ECE5DA] rounded w-3/4"></div>
          <div className="h-24 bg-[#F5EFE6] rounded"></div>
          <div className="h-64 bg-[#ECE5DA] rounded-xl"></div>
        </main>
      </div>
    );
  }

  if (error || !story) {
    return (
      <div className="min-h-screen bg-[#FBF9F5] font-serif">
        <NewspaperHeader user={user} />
        <main className="max-w-3xl mx-auto px-4 py-20 text-center font-sans">
          <div className="w-16 h-16 mx-auto mb-4 text-[#8C2524] flex items-center justify-center rounded-full bg-red-100">
            ⚠️
          </div>
          <h2 className="text-2xl font-bold text-[#181615] mb-2">Story Not Found</h2>
          <p className="text-[#6C645C] mb-6">{error || "This story could not be retrieved."}</p>
          <Link
            href="/stories"
            className="px-5 py-2.5 bg-[#181615] text-[#FBF9F5] font-semibold rounded-lg hover:opacity-90 transition"
          >
            ← Back to Developing Stories
          </Link>
        </main>
      </div>
    );
  }

  const filteredArticles = story.articles.filter((art) => {
    if (activePerspective === "ALL") return true;
    return art.relationship_type.toUpperCase() === activePerspective;
  });

  return (
    <div className="min-h-screen bg-[#FBF9F5] text-[#181615] antialiased font-serif">
      <NewspaperHeader user={user} />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Navigation Breadcrumb */}
        <div className="mb-6 font-sans text-xs flex items-center gap-2 text-[#6C645C]">
          <Link href="/stories" className="hover:text-[#181615] transition">
            ← Developing Stories
          </Link>
          <span>/</span>
          {story.primary_topic_name && (
            <>
              <span className="uppercase font-semibold text-[#8C2524]">{story.primary_topic_name}</span>
              <span>/</span>
            </>
          )}
          <span className="truncate max-w-xs text-[#181615]">{story.title}</span>
        </div>

        {/* Story Header */}
        <header className="border-b-2 border-[#181615] pb-8 mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            {getStatusBadge(story.status)}
            <span className="text-xs font-sans text-[#6C645C]">
              First reported {formatTimestamp(story.first_published_at)} • Updated {formatTimestamp(story.last_updated_at)}
            </span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-black font-serif tracking-tight leading-tight mb-4">
            {story.title}
          </h1>

          {story.summary && (
            <div className="p-4 sm:p-5 bg-[#F5EFE6] border-l-4 border-[#181615] rounded-r-lg mb-6">
              <div className="text-xs uppercase font-sans font-bold tracking-widest text-[#6C645C] mb-1">
                Story Synthesis & Editorial Overview
              </div>
              <p className="text-base sm:text-lg text-[#332E29] leading-relaxed font-light">
                {story.summary}
              </p>
            </div>
          )}

          {/* Conflict / Reports Differ Alert */}
          {story.has_conflicts && (
            <div className="mb-6 p-4 bg-amber-50 border border-amber-300 rounded-xl flex items-start gap-3 font-sans text-sm">
              <span className="text-xl">⚠️</span>
              <div>
                <h4 className="font-bold text-amber-900">Different Accounts Reported</h4>
                <p className="text-amber-800 mt-0.5">
                  {story.conflict_note || "Independent publishers are reporting materially different details or timelines on this story."}
                </p>
              </div>
            </div>
          )}

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-sans text-center bg-white p-4 rounded-xl border border-[#ECE5DA] shadow-sm">
            <div>
              <div className="text-xl font-bold text-[#181615]">{story.independent_source_count}</div>
              <div className="text-xs text-[#6C645C] uppercase tracking-wider">Independent Sources</div>
            </div>
            <div>
              <div className="text-xl font-bold text-[#181615]">{story.article_count}</div>
              <div className="text-xs text-[#6C645C] uppercase tracking-wider">Total Reports</div>
            </div>
            <div>
              <div className="text-xl font-bold text-[#181615]">{story.sources.length}</div>
              <div className="text-xs text-[#6C645C] uppercase tracking-wider">Publishers</div>
            </div>
            <div>
              <div className="text-xl font-bold text-emerald-700">
                {Math.round(story.importance_score * 100)}%
              </div>
              <div className="text-xs text-[#6C645C] uppercase tracking-wider">Story Importance</div>
            </div>
          </div>
        </header>

        {/* Section 1: Chronological Timeline */}
        <section className="mb-12">
          <div className="flex items-center justify-between gap-4 mb-6 border-b border-[#ECE5DA] pb-3">
            <h2 className="text-2xl font-bold font-serif uppercase tracking-tight flex items-center gap-2">
              <span>⏱️</span> Chronological Timeline
            </h2>
            <span className="text-xs font-sans text-[#6C645C]">
              {story.timeline.length} {story.timeline.length === 1 ? "Event" : "Key Events"}
            </span>
          </div>

          <div className="relative border-l-2 border-[#D3CBB9] ml-4 pl-6 space-y-6">
            {story.timeline.map((item) => (
              <div key={item.id} className="relative group">
                {/* Timeline Dot */}
                <div className="absolute -left-[31px] top-1.5 w-3.5 h-3.5 rounded-full bg-[#181615] border-2 border-white group-hover:scale-125 transition-transform"></div>

                <div className="bg-white border border-[#ECE5DA] rounded-xl p-4 shadow-sm group-hover:border-[#8C2524]/60 transition">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2 font-sans">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[#181615]">{item.source_name}</span>
                      {getRelationshipBadge(item.relationship_type)}
                    </div>
                    <span className="text-xs text-[#6C645C] font-mono">
                      {formatTimestamp(item.published_at)}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold font-serif mb-2 leading-snug">
                    <Link
                      href={`/article/${item.article_id}`}
                      className="hover:text-[#8C2524] transition"
                    >
                      {item.title}
                    </Link>
                  </h3>

                  {item.snippet && (
                    <p className="text-sm text-[#4A443E] line-clamp-2 font-light">
                      {item.snippet}
                    </p>
                  )}

                  <div className="mt-3 flex items-center justify-between font-sans text-xs">
                    <Link
                      href={`/article/${item.article_id}`}
                      className="text-[#8C2524] font-semibold hover:underline flex items-center gap-1"
                    >
                      Read Full Report →
                    </Link>
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#8C827A] hover:text-[#181615]"
                      >
                        Publisher Link ↗
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Section 2: Multi-Source Coverage & Perspectives */}
        <section className="mb-12">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 border-b border-[#ECE5DA] pb-3">
            <h2 className="text-2xl font-bold font-serif uppercase tracking-tight flex items-center gap-2">
              <span>🌐</span> Multi-Source Coverage
            </h2>

            {/* Perspectives Filter Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto font-sans text-xs pb-1 sm:pb-0">
              {["ALL", "PRIMARY", "UPDATE", "ANALYSIS", "REACTION", "BACKGROUND"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActivePerspective(tab)}
                  className={`px-3 py-1.5 rounded-full transition ${
                    activePerspective === tab
                      ? "bg-[#181615] text-white font-bold"
                      : "bg-[#ECE5DA] text-[#6C645C] hover:bg-[#DDD5C7]"
                  }`}
                >
                  {tab === "ALL" ? "All Perspectives" : tab.charAt(0) + tab.slice(1).toLowerCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {filteredArticles.map((art) => (
              <div
                key={art.id}
                className="bg-white border border-[#ECE5DA] rounded-xl p-5 shadow-sm flex flex-col justify-between hover:shadow-md transition"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2 font-sans">
                    <span className="text-xs font-bold text-[#181615]">
                      {art.source_name}
                    </span>
                    {getRelationshipBadge(art.relationship_type)}
                  </div>

                  <h3 className="text-base sm:text-lg font-bold font-serif mb-2 leading-snug">
                    <Link
                      href={`/article/${art.article_id}`}
                      className="hover:text-[#8C2524] transition"
                    >
                      {art.title}
                    </Link>
                  </h3>

                  {art.summary && (
                    <p className="text-xs sm:text-sm text-[#4A443E] line-clamp-3 font-light mb-4">
                      {art.summary}
                    </p>
                  )}
                </div>

                <div className="border-t border-[#ECE5DA] pt-3 mt-2 flex items-center justify-between text-xs font-sans text-[#6C645C]">
                  <span>{art.reading_time_minutes} min read</span>
                  <Link
                    href={`/article/${art.article_id}`}
                    className="font-semibold text-[#8C2524] hover:underline"
                  >
                    View Report →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Section 3: Covered Sources Directory */}
        <section className="mb-12 bg-white border border-[#ECE5DA] rounded-xl p-6 shadow-sm font-sans">
          <h3 className="text-sm font-bold uppercase tracking-wider text-[#6C645C] mb-3">
            Participating News Publishers ({story.sources.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {story.sources.map((source, idx) => (
              <span
                key={idx}
                className="px-3 py-1 text-xs font-semibold bg-[#F5EFE6] text-[#181615] rounded-md border border-[#ECE5DA]"
              >
                📰 {source}
              </span>
            ))}
          </div>
        </section>

        {/* Section 4: Related Stories */}
        {related.length > 0 && (
          <section className="border-t-2 border-[#181615] pt-8">
            <h2 className="text-2xl font-bold font-serif uppercase tracking-tight mb-6">
              Related Developing Stories
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {related.map((rel) => (
                <Link
                  key={rel.id}
                  href={`/stories/${rel.slug}`}
                  className="bg-white border border-[#ECE5DA] rounded-xl p-4 shadow-sm hover:border-[#8C2524]/60 transition flex flex-col justify-between"
                >
                  <div>
                    <div className="mb-2">{getStatusBadge(rel.status)}</div>
                    <h3 className="text-sm font-bold font-serif line-clamp-2 mb-2 leading-snug">
                      {rel.title}
                    </h3>
                  </div>
                  <div className="text-xs font-sans text-[#6C645C] mt-2">
                    {rel.independent_source_count} {rel.independent_source_count === 1 ? "Source" : "Sources"}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
