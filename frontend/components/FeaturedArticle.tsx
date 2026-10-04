"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Article } from "@/types";
import { ArticleMetadata } from "./ArticleMetadata";
import { Bookmark, Heart, ArrowRight, Sparkles } from "lucide-react";
import { saveArticle, unsaveArticle, likeArticle, unlikeArticle } from "@/lib/api";

interface FeaturedArticleProps {
  article: Article;
  token?: string | null;
  onActionComplete?: (action: string, articleId: string) => void;
}

export function FeaturedArticle({
  article,
  token,
  onActionComplete,
}: FeaturedArticleProps) {
  const [isSaved, setIsSaved] = useState<boolean>(Boolean(article.is_saved));
  const [isLiked, setIsLiked] = useState<boolean>(Boolean(article.is_liked));
  const [feedback, setFeedback] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setFeedback(msg);
    setTimeout(() => setFeedback(null), 2500);
  };

  const handleSaveToggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!token) {
      showToast("Sign in to save stories");
      return;
    }
    try {
      if (isSaved) {
        await unsaveArticle(article.id, token);
        setIsSaved(false);
        showToast("Removed from saved stories");
        onActionComplete?.("UNSAVE", article.id);
      } else {
        await saveArticle(article.id, token);
        setIsSaved(true);
        showToast("Saved to reading list");
        onActionComplete?.("SAVE", article.id);
      }
    } catch {
      showToast("Error updating bookmark");
    }
  };

  const handleLikeToggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!token) {
      showToast("Sign in to like stories");
      return;
    }
    try {
      if (isLiked) {
        await unlikeArticle(article.id, token);
        setIsLiked(false);
        showToast("Like removed");
        onActionComplete?.("UNLIKE", article.id);
      } else {
        await likeArticle(article.id, token);
        setIsLiked(true);
        showToast("Story liked");
        onActionComplete?.("LIKE", article.id);
      }
    } catch {
      showToast("Error updating like");
    }
  };

  return (
    <section className="bg-white border-2 border-[#181615] p-6 sm:p-8 lg:p-10 mb-10 shadow-sm relative">
      {/* Top Lead Story Label */}
      <div className="flex items-center justify-between pb-4 mb-6 border-b border-[#E4DCCF]">
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-widest">
            Lead Story
          </span>
          <span className="text-xs font-serif italic text-[#6C645C]">
            Today's top curated report
          </span>
        </div>

        {feedback && (
          <span className="text-xs font-semibold text-[#8C2524] animate-pulse">
            {feedback}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left Editorial Content */}
        <div className="lg:col-span-7 flex flex-col justify-between">
          <div>
            <ArticleMetadata
              source_name={article.source_name}
              published_at={article.published_at}
              reading_time_minutes={article.reading_time_minutes}
              author={article.author}
              topics={article.topics}
            />

            <Link href={`/article/${article.id}`} className="block mt-4 group">
              <h1 className="font-editorial-heading font-black text-2xl sm:text-3xl lg:text-4xl text-[#181615] leading-[1.18] group-hover:text-[#8C2524] transition-colors">
                {article.title}
              </h1>
            </Link>

            {article.description && (
              <p className="font-editorial-body text-base sm:text-lg text-[#3E3832] leading-relaxed mt-4 line-clamp-4">
                {article.description}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 mt-8 pt-5 border-t border-[#E8E1D5]">
            <Link
              href={`/article/${article.id}`}
              className="px-6 py-3 bg-[#181615] text-[#FAF8F5] text-xs sm:text-sm font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors flex items-center gap-2 shadow-sm"
            >
              <span>Read Full Story</span>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <div className="flex items-center gap-3 font-sans">
              <button
                onClick={handleLikeToggle}
                className={`p-2.5 border border-[#DCD3C7] rounded-sm hover:bg-[#F5EFEB] transition-colors flex items-center gap-1.5 text-xs font-semibold ${
                  isLiked ? "text-rose-700 border-rose-300 bg-rose-50" : "text-[#5C554E]"
                }`}
                title="Like this story"
              >
                <Heart className={`w-4 h-4 ${isLiked ? "fill-rose-700" : ""}`} />
                <span className="hidden sm:inline">{isLiked ? "Liked" : "Like"}</span>
              </button>

              <button
                onClick={handleSaveToggle}
                className={`p-2.5 border border-[#DCD3C7] rounded-sm hover:bg-[#F5EFEB] transition-colors flex items-center gap-1.5 text-xs font-semibold ${
                  isSaved ? "text-[#8C2524] border-red-300 bg-red-50" : "text-[#5C554E]"
                }`}
                title="Save story"
              >
                <Bookmark className={`w-4 h-4 ${isSaved ? "fill-[#8C2524]" : ""}`} />
                <span className="hidden sm:inline">{isSaved ? "Saved" : "Save"}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Hero Image */}
        {article.image_url && (
          <div className="lg:col-span-5">
            <Link href={`/article/${article.id}`} className="block group overflow-hidden bg-[#E8E1D5] rounded-sm aspect-[16/11] shadow-inner">
              <img
                src={article.image_url}
                alt={article.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
              />
            </Link>
            <div className="mt-2 text-right">
              <span className="text-[11px] text-[#7A7268] font-sans italic">
                Photo via editorial dispatch (Demo)
              </span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
