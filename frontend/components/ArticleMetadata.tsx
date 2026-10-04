"use client";

import React from "react";
import { TopicSummary } from "@/types";
import { Clock, BookOpen, ShieldAlert } from "lucide-react";

interface ArticleMetadataProps {
  source_name?: string | null;
  published_at?: string;
  reading_time_minutes?: number;
  author?: string | null;
  topics?: TopicSummary[];
  compact?: boolean;
}

export function formatTimeAgo(dateString?: string): string {
  if (!dateString) return "Recently";
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return "Just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  const days = Math.floor(diffInSeconds / 86400);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function ArticleMetadata({
  source_name,
  published_at,
  reading_time_minutes = 3,
  author,
  topics = [],
  compact = false,
}: ArticleMetadataProps) {
  const isDemo = source_name?.includes("[DEMO]") || true;

  return (
    <div className={`flex flex-wrap items-center gap-y-1.5 text-xs text-[#6C645C] font-sans ${compact ? "gap-x-2" : "gap-x-3"}`}>
      {/* Category / First Topic */}
      {topics.length > 0 && (
        <span className="font-bold uppercase tracking-wider text-[#8C2524]">
          {topics[0].name}
        </span>
      )}

      {topics.length > 0 && <span>•</span>}

      {/* Source */}
      {source_name && (
        <span className="font-semibold text-[#181615] flex items-center gap-1">
          <span>{source_name}</span>
          <span className="text-[10px] px-1 py-0.2 bg-amber-100 text-amber-900 border border-amber-300 font-mono rounded">
            DEMO
          </span>
        </span>
      )}

      {/* Author Byline */}
      {author && !compact && (
        <>
          <span>•</span>
          <span>By {author}</span>
        </>
      )}

      {/* Published time */}
      {published_at && (
        <>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-[#8C847B]" />
            <span>{formatTimeAgo(published_at)}</span>
          </span>
        </>
      )}

      {/* Reading time */}
      {reading_time_minutes > 0 && (
        <>
          <span>•</span>
          <span className="flex items-center gap-1">
            <BookOpen className="w-3 h-3 text-[#8C847B]" />
            <span>{reading_time_minutes} min read</span>
          </span>
        </>
      )}
    </div>
  );
}
