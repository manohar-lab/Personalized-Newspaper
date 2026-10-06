"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { fetchStories, fetchCurrentUser } from "@/lib/api";
import { StoryItem, User } from "@/types";

export default function StoriesPage() {
  const [stories, setStories] = useState<StoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
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

  const loadStories = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchStories(
        {
          status: statusFilter === "ALL" ? undefined : statusFilter,
          page,
          limit: 15,
        },
        token || undefined
      );
      setStories(res.items);
      setTotal(res.total);
    } catch (err: any) {
      setError(err.message || "Failed to load developing stories.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStories();
  }, [statusFilter, page, token]);

  const filteredStories = stories.filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.title.toLowerCase().includes(q) ||
      (s.summary && s.summary.toLowerCase().includes(q)) ||
      (s.primary_topic_name && s.primary_topic_name.toLowerCase().includes(q))
    );
  });

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "DEVELOPING":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 rounded-full animate-pulse">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            Developing Story
          </span>
        );
      case "ACTIVE":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold uppercase tracking-wider bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 rounded-full">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            Active
          </span>
        );
      case "STABLE":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium uppercase tracking-wider bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 rounded-full">
            Stable
          </span>
        );
      case "RESOLVED":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium uppercase tracking-wider bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 rounded-full">
            Resolved
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium uppercase tracking-wider bg-stone-500/10 text-stone-600 dark:text-stone-400 border border-stone-500/20 rounded-full">
            Archived
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#FBF9F5] text-[#181615] antialiased font-serif">
      <NewspaperHeader user={user} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Masthead Banner */}
        <div className="border-b-2 border-[#181615] pb-8 mb-10 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 text-xs font-bold uppercase tracking-widest bg-[#181615] text-[#FBF9F5] rounded">
              Multi-Source Story Intelligence
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight font-serif mb-4 uppercase">
            Developing Stories & Timelines
          </h1>
          <p className="max-w-2xl mx-auto text-base text-[#6C645C] font-sans font-light">
            Synthesized multi-source perspectives on major developing events. Understand how complex news stories evolve chronologically across independent publishers.
          </p>
        </div>

        {/* Controls: Search & Status Filters */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 mb-8 font-sans">
          {/* Search Box */}
          <div className="relative w-full md:w-96">
            <input
              type="text"
              placeholder="Search developing stories, topics..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2.5 pl-10 text-sm bg-white border border-[#ECE5DA] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#8C2524] transition-shadow shadow-sm"
            />
            <svg
              className="w-4 h-4 text-[#A89F91] absolute left-3.5 top-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          {/* Status Filters */}
          <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
            {[
              { label: "All Stories", value: "ALL" },
              { label: "⚡ Developing", value: "DEVELOPING" },
              { label: "Active", value: "ACTIVE" },
              { label: "Stable", value: "STABLE" },
              { label: "Archived", value: "ARCHIVED" },
            ].map((f) => (
              <button
                key={f.value}
                onClick={() => {
                  setStatusFilter(f.value);
                  setPage(1);
                }}
                className={`px-4 py-2 text-xs font-medium rounded-full whitespace-nowrap transition-all ${
                  statusFilter === f.value
                    ? "bg-[#181615] text-[#FBF9F5] font-bold shadow-sm"
                    : "bg-[#ECE5DA] text-[#6C645C] hover:bg-[#DDD5C7]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Story List */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="bg-white border border-[#ECE5DA] rounded-xl p-6 shadow-sm animate-pulse space-y-4"
              >
                <div className="h-5 bg-[#ECE5DA] rounded w-1/3"></div>
                <div className="h-7 bg-[#ECE5DA] rounded w-4/5"></div>
                <div className="h-16 bg-[#F5EFE6] rounded"></div>
                <div className="h-4 bg-[#ECE5DA] rounded w-2/3"></div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="p-8 text-center bg-red-50 border border-red-200 rounded-xl text-red-600 font-sans">
            <p className="font-semibold">{error}</p>
            <button
              onClick={loadStories}
              className="mt-4 px-4 py-2 text-xs font-semibold bg-[#8C2524] text-white rounded-lg hover:opacity-90 transition"
            >
              Try Again
            </button>
          </div>
        ) : filteredStories.length === 0 ? (
          <div className="p-16 text-center bg-white border border-dashed border-[#D3CBB9] rounded-2xl font-sans">
            <div className="w-16 h-16 mx-auto mb-4 text-[#A89F91] flex items-center justify-center rounded-full bg-[#F5EFE6]">
              📰
            </div>
            <h3 className="text-lg font-bold text-[#181615]">No Stories Found</h3>
            <p className="text-[#6C645C] text-sm mt-1 max-w-md mx-auto">
              There are currently no evolving stories matching your active filter. Check back soon as new multi-source reports arrive!
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredStories.map((story) => (
              <Link
                key={story.id}
                href={`/stories/${story.slug}`}
                className="group flex flex-col justify-between bg-white border border-[#ECE5DA] rounded-xl p-6 shadow-sm hover:shadow-md hover:border-[#8C2524]/60 transition-all"
              >
                <div>
                  {/* Top Metadata: Status & Topic */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    {getStatusBadge(story.status)}
                    {story.primary_topic_name && (
                      <span className="text-xs uppercase font-sans font-bold tracking-wider text-[#8C2524]">
                        {story.primary_topic_name}
                      </span>
                    )}
                  </div>

                  {/* Headline */}
                  <h2 className="text-xl font-bold font-serif leading-tight group-hover:text-[#8C2524] transition-colors mb-3">
                    {story.title}
                  </h2>

                  {/* Story Synthesis */}
                  <p className="text-sm font-serif text-[#4A443E] line-clamp-3 mb-4 leading-relaxed font-light">
                    {story.summary || "Multi-source coverage detailing evolving developments."}
                  </p>
                </div>

                {/* Footer Metrics */}
                <div className="border-t border-[#ECE5DA] pt-4 mt-2 flex items-center justify-between text-xs font-sans text-[#6C645C]">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 font-semibold text-[#181615]">
                      <span>🌐</span> {story.independent_source_count} {story.independent_source_count === 1 ? "Source" : "Sources"}
                    </span>
                    <span>•</span>
                    <span>{story.article_count} {story.article_count === 1 ? "Report" : "Reports"}</span>
                  </div>

                  <span className="font-semibold text-[#8C2524] group-hover:translate-x-0.5 transition-transform">
                    Explore Timeline →
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
