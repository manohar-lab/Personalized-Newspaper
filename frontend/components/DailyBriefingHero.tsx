"use client";

import React from "react";
import { NewsBriefingResponse, BriefingItemResponse } from "@/types";
import { Sparkles, RefreshCw, CheckCircle2, ArrowRight, Clock, Layers, Zap, BookOpen } from "lucide-react";
import Link from "next/link";

interface DailyBriefingHeroProps {
  briefing: NewsBriefingResponse | null;
  loading: boolean;
  onRefresh: () => void;
  refreshing: boolean;
}

export const DailyBriefingHero: React.FC<DailyBriefingHeroProps> = ({
  briefing,
  loading,
  onRefresh,
  refreshing,
}) => {
  if (loading) {
    return (
      <div className="mb-12 p-6 rounded-2xl bg-amber-500/5 border border-amber-500/20 animate-pulse">
        <div className="h-6 w-48 bg-amber-500/20 rounded mb-4"></div>
        <div className="h-4 w-96 bg-amber-500/10 rounded mb-8"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="h-44 bg-amber-500/10 rounded-xl"></div>
          <div className="h-44 bg-amber-500/10 rounded-xl"></div>
          <div className="h-44 bg-amber-500/10 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (!briefing) return null;

  const getTypeBadgeColor = (type: string) => {
    switch (type) {
      case "IMPORTANT":
        return "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30";
      case "UPDATED":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30";
      case "FOLLOW_UP":
        return "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30";
      case "FOR_YOU":
        return "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30";
      case "DISCOVERY":
        return "bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/30";
      default:
        return "bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30";
    }
  };

  return (
    <div className="mb-14 rounded-2xl bg-gradient-to-br from-amber-500/[0.07] via-background to-orange-500/[0.04] border border-amber-500/20 p-6 md:p-8 shadow-sm">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-amber-500/15">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-serif tracking-widest font-semibold bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30 uppercase">
              {briefing.greeting}
            </span>
            <span className="text-xs text-muted-foreground font-mono">
              {briefing.daypart} BRIEFING · v{briefing.version}
            </span>
          </div>
          <h2 className="text-2xl md:text-3xl font-serif font-bold text-foreground tracking-tight">
            What Changed Since Your Last Visit
          </h2>
          {briefing.intro && (
            <p className="mt-1.5 text-sm md:text-base text-muted-foreground font-sans">
              {briefing.intro}
            </p>
          )}
        </div>

        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="self-start sm:self-center inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium bg-secondary hover:bg-secondary/80 text-foreground border border-border transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-amber-500" : ""}`} />
          {refreshing ? "Updating..." : "Refresh Briefing"}
        </button>
      </div>

      {/* Caught Up State */}
      {briefing.is_caught_up && (
        <div className="py-10 text-center">
          <div className="w-12 h-12 rounded-full bg-emerald-500/15 text-emerald-500 mx-auto flex items-center justify-center mb-3">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-serif font-semibold text-foreground">
            You&apos;re All Caught Up
          </h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto mt-1">
            No major new developments have broken since your last session. Your full daily edition is ready below.
          </p>
        </div>
      )}

      {/* 3 Things To Know */}
      {!briefing.is_caught_up && briefing.top_items.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-4 h-4 text-amber-500" />
            <h3 className="text-xs font-mono uppercase tracking-widest font-semibold text-amber-700 dark:text-amber-300">
              3 Things To Know
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {briefing.top_items.map((item, idx) => (
              <div
                key={item.id}
                className="group relative flex flex-col justify-between rounded-xl bg-card/75 border border-border/80 p-5 hover:border-amber-500/40 hover:shadow-md transition-all"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2.5">
                    <span className="font-mono text-xs font-bold text-amber-500/80">
                      0{idx + 1}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase font-medium ${getTypeBadgeColor(
                        item.briefing_type
                      )}`}
                    >
                      {item.briefing_type.replace("_", " ")}
                    </span>
                  </div>

                  <h4 className="font-serif font-bold text-base text-foreground leading-snug line-clamp-2 group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
                    {item.headline}
                  </h4>

                  {item.summary && (
                    <p className="mt-2 text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                      {item.summary}
                    </p>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <span>{item.source_name}</span>
                    {item.source_count > 1 && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-secondary font-mono text-[10px]">
                        <Layers className="w-2.5 h-2.5" />
                        {item.independent_source_count} sources
                      </span>
                    )}
                  </div>

                  {item.story_id ? (
                    <Link
                      href={`/stories/${item.story_id}`}
                      className="inline-flex items-center gap-1 font-medium text-amber-600 dark:text-amber-400 hover:underline"
                    >
                      Read story <ArrowRight className="w-3 h-3" />
                    </Link>
                  ) : item.article_id ? (
                    <Link
                      href={`/articles/${item.article_id}`}
                      className="inline-flex items-center gap-1 font-medium text-amber-600 dark:text-amber-400 hover:underline"
                    >
                      Read <ArrowRight className="w-3 h-3" />
                    </Link>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* What Changed (Follow-ups & Updates) */}
      {!briefing.is_caught_up && briefing.what_changed.length > 0 && (
        <div className="mt-8 pt-6 border-t border-amber-500/15">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-4 h-4 text-amber-500" />
            <h3 className="text-xs font-mono uppercase tracking-widest font-semibold text-amber-700 dark:text-amber-300">
              What Changed Since You Read It
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {briefing.what_changed.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-3.5 p-4 rounded-xl bg-card/50 border border-border hover:border-amber-500/30 transition-all"
              >
                <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 mt-0.5">
                  <BookOpen className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 font-medium">
                      {item.briefing_type.replace("_", " ")}
                    </span>
                    {item.reason && (
                      <span className="text-[11px] text-muted-foreground truncate">
                        {item.reason}
                      </span>
                    )}
                  </div>
                  <h4 className="font-serif font-bold text-sm text-foreground leading-snug line-clamp-2">
                    {item.headline}
                  </h4>
                  {item.summary && (
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {item.summary}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
