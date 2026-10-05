"use client";

import React, { useState } from "react";
import Link from "next/link";
import { NewspaperStoryResponse } from "@/types";
import { Bookmark, Heart, ThumbsDown, ArrowUpRight, Sparkles, Clock } from "lucide-react";
import { saveArticle, unsaveArticle, likeArticle, unlikeArticle, markArticleNotInterested } from "@/lib/api";

interface EditionStoryCardProps {
  story: NewspaperStoryResponse;
  token?: string | null;
  layout?: "LEAD" | "FEATURE" | "STANDARD" | "COMPACT";
  onActionComplete?: (action: string, articleId: string) => void;
}

export function EditionStoryCard({
  story,
  token,
  layout = "STANDARD",
  onActionComplete,
}: EditionStoryCardProps) {
  const [isSaved, setIsSaved] = useState<boolean>(Boolean(story.is_saved));
  const [isLiked, setIsLiked] = useState<boolean>(Boolean(story.is_liked));
  const [isDismissed, setIsDismissed] = useState<boolean>(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  const showFeedback = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 2500);
  };

  const handleSaveToggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!token) {
      showFeedback("Sign in to save stories");
      return;
    }
    try {
      if (isSaved) {
        await unsaveArticle(story.article_id, token);
        setIsSaved(false);
        showFeedback("Removed bookmark");
        onActionComplete?.("UNSAVE", story.article_id);
      } else {
        await saveArticle(story.article_id, token);
        setIsSaved(true);
        showFeedback("Saved to reading list");
        onActionComplete?.("SAVE", story.article_id);
      }
    } catch {
      showFeedback("Error saving");
    }
  };

  const handleLikeToggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!token) {
      showFeedback("Sign in to like stories");
      return;
    }
    try {
      if (isLiked) {
        await unlikeArticle(story.article_id, token);
        setIsLiked(false);
        showFeedback("Like removed");
        onActionComplete?.("UNLIKE", story.article_id);
      } else {
        await likeArticle(story.article_id, token);
        setIsLiked(true);
        showFeedback("Story liked");
        onActionComplete?.("LIKE", story.article_id);
      }
    } catch {
      showFeedback("Error liking");
    }
  };

  const handleNotInterested = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!token) {
      showFeedback("Sign in to personalize");
      return;
    }
    try {
      await markArticleNotInterested(story.article_id, token);
      setIsDismissed(true);
      showFeedback("Dismissed");
      onActionComplete?.("NOT_INTERESTED", story.article_id);
    } catch {
      showFeedback("Error updating");
    }
  };

  if (isDismissed) {
    return (
      <div className="p-3 bg-[#F2EFE9] border border-dashed border-[#DCD3C7] text-xs text-[#7A7268] font-sans flex items-center justify-between">
        <span>Story dismissed from your daily edition.</span>
        <span className="font-semibold text-[#181615]">Removed</span>
      </div>
    );
  }

  // 1. LEAD STORY LAYOUT
  if (layout === "LEAD" || story.is_lead) {
    return (
      <section className="bg-white border-2 border-[#181615] p-6 sm:p-8 lg:p-10 mb-8 shadow-sm relative">
        <div className="flex flex-wrap items-center justify-between pb-3 mb-6 border-b border-[#E4DCCF] gap-2">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-widest">
              Lead Story
            </span>
            {story.personalization_reason && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#FAF3EB] text-[#8C2524] text-[11px] font-medium rounded border border-[#EADBCC]">
                <Sparkles className="w-3 h-3 text-[#8C2524]" />
                <span>{story.personalization_reason}</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 text-xs text-[#6C645C]">
            <span className="font-semibold text-[#181615]">{story.source_name}</span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {story.reading_time_minutes} min read
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          <div className="lg:col-span-7 flex flex-col justify-between">
            <div>
              <Link href={`/article/${story.article_id}`} className="block group">
                <h1 className="font-editorial-heading font-black text-2xl sm:text-3xl lg:text-4xl text-[#181615] leading-[1.18] group-hover:text-[#8C2524] transition-colors">
                  {story.title}
                </h1>
              </Link>

              {story.summary && (
                <p className="font-editorial-body text-base sm:text-lg text-[#3E3832] leading-relaxed mt-4 line-clamp-4">
                  {story.summary}
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4 mt-8 pt-5 border-t border-[#E8E1D5]">
              <Link
                href={`/article/${story.article_id}`}
                className="px-6 py-3 bg-[#181615] text-[#FAF8F5] text-xs sm:text-sm font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors flex items-center gap-2 shadow-sm"
              >
                <span>Read Full Story</span>
                <ArrowUpRight className="w-4 h-4" />
              </Link>

              <div className="flex items-center gap-2 font-sans">
                {feedbackMsg && (
                  <span className="text-xs font-semibold text-[#8C2524] animate-pulse">
                    {feedbackMsg}
                  </span>
                )}
                <button
                  onClick={handleLikeToggle}
                  className={`p-2 border border-[#DCD3C7] rounded-sm hover:bg-[#F5EFEB] transition-colors flex items-center gap-1.5 text-xs font-semibold ${
                    isLiked ? "text-rose-700 border-rose-300 bg-rose-50" : "text-[#5C554E]"
                  }`}
                  title="Like"
                >
                  <Heart className={`w-4 h-4 ${isLiked ? "fill-rose-700" : ""}`} />
                  <span className="hidden sm:inline">{isLiked ? "Liked" : "Like"}</span>
                </button>
                <button
                  onClick={handleSaveToggle}
                  className={`p-2 border border-[#DCD3C7] rounded-sm hover:bg-[#F5EFEB] transition-colors flex items-center gap-1.5 text-xs font-semibold ${
                    isSaved ? "text-[#8C2524] border-red-300 bg-red-50" : "text-[#5C554E]"
                  }`}
                  title="Save"
                >
                  <Bookmark className={`w-4 h-4 ${isSaved ? "fill-[#8C2524]" : ""}`} />
                  <span className="hidden sm:inline">{isSaved ? "Saved" : "Save"}</span>
                </button>
              </div>
            </div>
          </div>

          {story.top_image_url && (
            <div className="lg:col-span-5">
              <Link href={`/article/${story.article_id}`} className="block group overflow-hidden bg-[#E8E1D5] rounded-sm aspect-[16/11] shadow-inner">
                <img
                  src={story.top_image_url}
                  alt={story.title}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                />
              </Link>
            </div>
          )}
        </div>
      </section>
    );
  }

  // 2. FEATURE STORY LAYOUT
  if (layout === "FEATURE") {
    return (
      <article className="group bg-white p-5 border border-[#E4DCCF] hover:border-[#181615] hover:shadow-md transition-all flex flex-col justify-between">
        <div>
          {story.top_image_url && (
            <div className="overflow-hidden bg-[#E8E1D5] aspect-[16/10] mb-3.5 rounded-sm">
              <img
                src={story.top_image_url}
                alt={story.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                loading="lazy"
              />
            </div>
          )}

          <div className="flex items-center justify-between gap-2 text-xs text-[#6C645C] mb-2">
            <span className="font-bold text-[#181615]">{story.source_name}</span>
            {story.personalization_reason && (
              <span className="inline-flex items-center gap-1 text-[11px] text-[#8C2524] bg-[#FAF3EB] px-2 py-0.5 rounded border border-[#EADBCC] line-clamp-1">
                <Sparkles className="w-3 h-3 shrink-0" />
                <span className="truncate">{story.personalization_reason}</span>
              </span>
            )}
          </div>

          <Link href={`/article/${story.article_id}`} className="block mt-1">
            <h3 className="font-editorial-heading font-black text-xl text-[#181615] leading-snug group-hover:text-[#8C2524] transition-colors">
              {story.title}
            </h3>
          </Link>

          {story.summary && (
            <p className="font-editorial-body text-sm text-[#4E473F] line-clamp-3 mt-2.5 leading-relaxed">
              {story.summary}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between mt-5 pt-3 border-t border-[#EFE9DF] text-xs text-[#7A7268]">
          <Link
            href={`/article/${story.article_id}`}
            className="inline-flex items-center gap-1 font-bold text-[#181615] hover:text-[#8C2524] transition-colors"
          >
            <span>Read Story</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>

          <div className="flex items-center gap-1.5">
            {feedbackMsg && (
              <span className="text-[11px] font-semibold text-[#8C2524]">{feedbackMsg}</span>
            )}
            <button
              onClick={handleLikeToggle}
              className={`p-1.5 rounded hover:bg-[#EFE8DC] transition-colors ${
                isLiked ? "text-rose-700" : "text-[#7A7268]"
              }`}
              title="Like"
            >
              <Heart className={`w-3.5 h-3.5 ${isLiked ? "fill-rose-700" : ""}`} />
            </button>
            <button
              onClick={handleSaveToggle}
              className={`p-1.5 rounded hover:bg-[#EFE8DC] transition-colors ${
                isSaved ? "text-[#8C2524]" : "text-[#7A7268]"
              }`}
              title="Save"
            >
              <Bookmark className={`w-3.5 h-3.5 ${isSaved ? "fill-[#8C2524]" : ""}`} />
            </button>
            <button
              onClick={handleNotInterested}
              className="p-1.5 rounded hover:bg-[#EFE8DC] text-[#7A7268] hover:text-rose-800 transition-colors"
              title="Not interested"
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </article>
    );
  }

  // 3. COMPACT STORY LAYOUT
  if (layout === "COMPACT") {
    return (
      <article className="group py-3.5 border-b border-[#E8E1D5] hover:bg-[#F7F3EB]/60 transition-colors">
        <div className="flex items-center justify-between text-[11px] text-[#7A7268] mb-1">
          <span className="font-semibold text-[#181615]">{story.source_name}</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {story.reading_time_minutes}m
          </span>
        </div>

        <Link href={`/article/${story.article_id}`} className="block">
          <h4 className="font-editorial-heading font-bold text-base text-[#181615] leading-snug group-hover:text-[#8C2524] transition-colors">
            {story.title}
          </h4>
        </Link>

        {story.summary && (
          <p className="font-editorial-body text-xs text-[#5C544C] line-clamp-2 mt-1 leading-relaxed">
            {story.summary}
          </p>
        )}
      </article>
    );
  }

  // 4. STANDARD STORY LAYOUT (Horizontal / Flex)
  return (
    <article className="group relative flex flex-col sm:flex-row gap-4 py-4 border-b border-[#E8E1D5] hover:bg-[#F7F3EB]/60 transition-colors">
      {story.top_image_url && (
        <div className="sm:w-1/3 shrink-0 overflow-hidden bg-[#E8E1D5] aspect-[16/10] sm:aspect-[4/3] rounded-sm">
          <img
            src={story.top_image_url}
            alt={story.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            loading="lazy"
          />
        </div>
      )}

      <div className="flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between gap-2 text-xs text-[#6C645C] mb-1.5">
            <span className="font-bold text-[#181615]">{story.source_name}</span>
            {story.personalization_reason && (
              <span className="inline-flex items-center gap-1 text-[11px] text-[#8C2524] bg-[#FAF3EB] px-2 py-0.5 rounded border border-[#EADBCC] line-clamp-1">
                <Sparkles className="w-3 h-3 shrink-0" />
                <span className="truncate">{story.personalization_reason}</span>
              </span>
            )}
          </div>

          <Link href={`/article/${story.article_id}`} className="block mt-1">
            <h3 className="font-editorial-heading font-bold text-lg text-[#181615] leading-snug group-hover:text-[#8C2524] transition-colors">
              {story.title}
            </h3>
          </Link>

          {story.summary && (
            <p className="font-editorial-body text-sm text-[#4E473F] line-clamp-2 mt-1.5 leading-relaxed">
              {story.summary}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#EFE9DF] text-xs text-[#7A7268]">
          <Link
            href={`/article/${story.article_id}`}
            className="inline-flex items-center gap-1 font-semibold text-[#181615] hover:text-[#8C2524] transition-colors"
          >
            <span>Read story</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>

          <div className="flex items-center gap-2">
            {feedbackMsg && (
              <span className="text-[11px] font-semibold text-[#8C2524] animate-fade-in">
                {feedbackMsg}
              </span>
            )}
            <button
              onClick={handleLikeToggle}
              className={`p-1.5 rounded hover:bg-[#EFE8DC] transition-colors ${
                isLiked ? "text-rose-700" : "text-[#7A7268]"
              }`}
              title="Like"
            >
              <Heart className={`w-3.5 h-3.5 ${isLiked ? "fill-rose-700" : ""}`} />
            </button>
            <button
              onClick={handleSaveToggle}
              className={`p-1.5 rounded hover:bg-[#EFE8DC] transition-colors ${
                isSaved ? "text-[#8C2524]" : "text-[#7A7268]"
              }`}
              title="Save"
            >
              <Bookmark className={`w-3.5 h-3.5 ${isSaved ? "fill-[#8C2524]" : ""}`} />
            </button>
            <button
              onClick={handleNotInterested}
              className="p-1.5 rounded hover:bg-[#EFE8DC] text-[#7A7268] hover:text-rose-800 transition-colors"
              title="Not interested"
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}
