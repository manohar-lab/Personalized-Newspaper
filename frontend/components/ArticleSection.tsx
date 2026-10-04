"use client";

import React from "react";
import { NewspaperSection as NewspaperSectionType } from "@/types";
import { ArticleCard } from "./ArticleCard";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

interface ArticleSectionProps {
  section: NewspaperSectionType;
  token?: string | null;
  onActionComplete?: (action: string, articleId: string) => void;
}

export function ArticleSection({
  section,
  token,
  onActionComplete,
}: ArticleSectionProps) {
  const { topic, articles } = section;

  if (!articles || articles.length === 0) {
    return null;
  }

  const primaryArticle = articles[0];
  const secondaryArticles = articles.slice(1);

  return (
    <section className="mb-14">
      {/* Section Masthead Title */}
      <div className="flex items-center justify-between pb-2 mb-6 border-b-2 border-[#181615]">
        <div className="flex items-baseline gap-3">
          <h2 className="font-editorial-heading font-black text-xl sm:text-2xl text-[#181615] uppercase tracking-wider">
            {topic.name}
          </h2>
          <span className="text-xs font-sans text-[#7A7268]">
            {articles.length} {articles.length === 1 ? "story" : "stories"}
          </span>
        </div>

        <Link
          href={`/newspaper?topic=${topic.slug}`}
          className="text-xs font-sans font-semibold text-[#8C2524] hover:underline flex items-center gap-0.5"
        >
          <span>View all</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Dynamic Editorial Grid */}
      {articles.length === 1 ? (
        <div className="max-w-3xl">
          <ArticleCard
            article={primaryArticle}
            token={token}
            layout="horizontal"
            onActionComplete={onActionComplete}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Lead Story in this section */}
          <div className="lg:col-span-7">
            <ArticleCard
              article={primaryArticle}
              token={token}
              layout="standard"
              onActionComplete={onActionComplete}
            />
          </div>

          {/* Secondary Stacked Articles in this section */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {secondaryArticles.map((art) => (
              <ArticleCard
                key={art.id}
                article={art}
                token={token}
                layout="horizontal"
                onActionComplete={onActionComplete}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
