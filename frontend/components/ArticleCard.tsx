"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Article } from "@/types";
import { ArticleMetadata } from "./ArticleMetadata";
import { Bookmark, Heart, ThumbsDown, ArrowUpRight, Check } from "lucide-react";
import { saveArticle, unsaveArticle, likeArticle, unlikeArticle, markArticleNotInterested } from "@/lib/api";

interface ArticleCardProps {
  article: Article;
  token?: string | null;
  layout?: "lead" | "standard" | "compact" | "horizontal";
  onActionComplete?: (action: string, articleId: string) => void;
}

export function ArticleCard({
  article,
  token,
  layout = "standard",
  onActionComplete,
}: ArticleCardProps) {
  const [isSaved, setIsSaved] = useState<boolean>(Boolean(article.is_saved));
  const [isLiked, setIsLiked] = useState<boolean>(Boolean(article.is_liked));
  const [isNotInterested, setIsNotInterested] = useState<boolean>(Boolean(article.is_not_interested));
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
        await unsaveArticle(article.id, token);
        setIsSaved(false);
        showFeedback("Removed from saved");
        onActionComplete?.("UNSAVE", article.id);
      } else {
        await saveArticle(article.id, token);
        setIsSaved(true);
        showFeedback("Saved to reading list");
        onActionComplete?.("SAVE", article.id);
      }
    } catch {
      showFeedback("Error updating bookmark");
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
        await unlikeArticle(article.id, token);
        setIsLiked(false);
        showFeedback("Like removed");
        onActionComplete?.("UNLIKE", article.id);
      } else {
        await likeArticle(article.id, token);
        setIsLiked(true);
        showFeedback("Story liked");
        onActionComplete?.("LIKE", article.id);
      }
    } catch {
      showFeedback("Error liking story");
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
      await markArticleNotInterested(article.id, token);
      setIsNotInterested(true);
      showFeedback("Marked not interested");
      onActionComplete?.("NOT_INTERESTED", article.id);
    } catch {
      showFeedback("Error updating preference");
    }
  };

  if (isNotInterested) {
    return (
      <div className="p-4 bg-[#F2EFE9] border border-dashed border-[#DCD3C7] text-xs text-[#7A7268] font-sans flex items-center justify-between">
        <span>Story removed from your newspaper recommendations.</span>
        <span className="font-semibold text-[#181615]">Dismissed</span>
      </div>
    );
  }

  if (layout === "horizontal") {
    return (
      <article className="group relative flex flex-col sm:flex-row gap-4 py-4 border-b border-[#E8E1D5] hover:bg-[#F7F3EB]/60 transition-colors">
        {article.image_url && (
          <div className="sm:w-1/3 shrink-0 overflow-hidden bg-[#E8E1D5] aspect-[16/10] sm:aspect-[4/3] rounded-sm">
            <img
              src={article.image_url}
              alt={article.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              loading="lazy"
            />
          </div>
        )}
        <div className="flex-1 flex flex-col justify-between">
          <div>
            <ArticleMetadata
              source_name={article.source_name}
              published_at={article.published_at}
              reading_time_minutes={article.reading_time_minutes}
              topics={article.topics}
              compact
            />
            <Link href={`/article/${article.id}`} className="block mt-1.5">
              <h3 className="font-editorial-heading font-bold text-lg sm:text-xl text-[#181615] leading-snug group-hover:text-[#8C2524] transition-colors">
                {article.title}
              </h3>
            </Link>
            {article.description && (
              <p className="font-editorial-body text-sm text-[#4E473F] line-clamp-2 mt-1.5 leading-relaxed">
                {article.description}
              </p>
            )}
          </div>

          <div className="flex items-center justify-between mt-3 pt-2 border-t border-[#EFE9DF] text-xs text-[#7A7268]">
            <Link
              href={`/article/${article.id}`}
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
                title={isLiked ? "Unlike" : "Like story"}
              >
                <Heart className={`w-3.5 h-3.5 ${isLiked ? "fill-rose-700" : ""}`} />
              </button>
              <button
                onClick={handleSaveToggle}
                className={`p-1.5 rounded hover:bg-[#EFE8DC] transition-colors ${
                  isSaved ? "text-[#8C2524]" : "text-[#7A7268]"
                }`}
                title={isSaved ? "Remove bookmark" : "Save story"}
              >
                <Bookmark className={`w-3.5 h-3.5 ${isSaved ? "fill-[#8C2524]" : ""}`} />
              </button>
            </div>
          </div>
        </div>
      </article>
    );
  }

  if (layout === "compact") {
    return (
      <article className="group py-3 border-b border-[#E8E1D5] hover:bg-[#F7F3EB]/50 transition-colors">
        <ArticleMetadata
          source_name={article.source_name}
          published_at={article.published_at}
          reading_time_minutes={article.reading_time_minutes}
          topics={article.topics}
          compact
        />
        <Link href={`/article/${article.id}`} className="block mt-1">
          <h4 className="font-editorial-heading font-bold text-base text-[#181615] leading-snug group-hover:text-[#8C2524] transition-colors">
            {article.title}
          </h4>
        </Link>
        {article.description && (
          <p className="font-editorial-body text-xs text-[#5C544C] line-clamp-2 mt-1">
            {article.description}
          </p>
        )}
      </article>
    );
  }

  // Standard vertical card
  return (
    <article className="group flex flex-col justify-between p-4 bg-white/70 border border-[#E4DCCF] hover:border-[#181615] hover:shadow-md transition-all">
      <div>
        {article.image_url && (
          <div className="overflow-hidden bg-[#E8E1D5] aspect-[16/10] mb-3">
            <img
              src={article.image_url}
              alt={article.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              loading="lazy"
            />
          </div>
        )}

        <ArticleMetadata
          source_name={article.source_name}
          published_at={article.published_at}
          reading_time_minutes={article.reading_time_minutes}
          topics={article.topics}
          compact
        />

        <Link href={`/article/${article.id}`} className="block mt-2">
          <h3 className="font-editorial-heading font-bold text-lg text-[#181615] leading-snug group-hover:text-[#8C2524] transition-colors">
            {article.title}
          </h3>
        </Link>

        {article.description && (
          <p className="font-editorial-body text-sm text-[#4E473F] line-clamp-3 mt-2 leading-relaxed">
            {article.description}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-[#EFE9DF] text-xs text-[#7A7268]">
        <Link
          href={`/article/${article.id}`}
          className="inline-flex items-center gap-1 font-bold text-[#181615] hover:text-[#8C2524] transition-colors"
        >
          <span>Read Story</span>
          <ArrowUpRight className="w-3.5 h-3.5" />
        </Link>

        <div className="flex items-center gap-2">
          {feedbackMsg && (
            <span className="text-[11px] font-semibold text-[#8C2524]">
              {feedbackMsg}
            </span>
          )}
          <button
            onClick={handleLikeToggle}
            className={`p-1.5 rounded hover:bg-[#EFE8DC] transition-colors ${
              isLiked ? "text-rose-700" : "text-[#7A7268]"
            }`}
            title={isLiked ? "Liked" : "Like story"}
          >
            <Heart className={`w-4 h-4 ${isLiked ? "fill-rose-700" : ""}`} />
          </button>
          <button
            onClick={handleSaveToggle}
            className={`p-1.5 rounded hover:bg-[#EFE8DC] transition-colors ${
              isSaved ? "text-[#8C2524]" : "text-[#7A7268]"
            }`}
            title={isSaved ? "Saved" : "Save for later"}
          >
            <Bookmark className={`w-4 h-4 ${isSaved ? "fill-[#8C2524]" : ""}`} />
          </button>
          <button
            onClick={handleNotInterested}
            className="p-1.5 rounded hover:bg-[#EFE8DC] text-[#7A7268] hover:text-rose-800 transition-colors"
            title="Not interested in this story"
          >
            <ThumbsDown className="w-4 h-4" />
          </button>
        </div>
      </div>
    </article>
  );
}
