"use client";

import React from "react";
import { NewspaperSectionResponse } from "@/types";
import { EditionStoryCard } from "./EditionStoryCard";

interface EditionSectionProps {
  section: NewspaperSectionResponse;
  token?: string | null;
  onActionComplete?: (action: string, articleId: string) => void;
}

export function EditionSection({
  section,
  token,
  onActionComplete,
}: EditionSectionProps) {
  const { name, display_name, stories } = section;

  if (!stories || stories.length === 0) {
    return null;
  }

  // Split stories by layout type
  const featureStories = stories.filter((s) => s.layout_type === "FEATURE");
  const standardStories = stories.filter((s) => s.layout_type === "STANDARD" || !s.layout_type);
  const compactStories = stories.filter((s) => s.layout_type === "COMPACT");
  const otherStories = stories.filter(
    (s) => s.layout_type !== "FEATURE" && s.layout_type !== "STANDARD" && s.layout_type !== "COMPACT" && !s.is_lead
  );

  return (
    <section className="mb-12">
      {/* Section Masthead Header */}
      <div className="flex items-baseline justify-between pb-2 mb-6 border-b-2 border-[#181615]">
        <div className="flex items-baseline gap-3">
          <h2 className="font-editorial-heading font-black text-xl sm:text-2xl text-[#181615] uppercase tracking-wider">
            {display_name || name}
          </h2>
          <span className="text-xs font-sans text-[#7A7268]">
            {stories.length} {stories.length === 1 ? "story" : "stories"}
          </span>
        </div>
      </div>

      {/* Feature stories grid (2-column on desktop) */}
      {featureStories.length > 0 && (
        <div className={`grid grid-cols-1 ${featureStories.length > 1 ? "md:grid-cols-2" : ""} gap-6 mb-6`}>
          {featureStories.map((story) => (
            <EditionStoryCard
              key={story.id}
              story={story}
              token={token}
              layout="FEATURE"
              onActionComplete={onActionComplete}
            />
          ))}
        </div>
      )}

      {/* Standard & Compact stories combined grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Main Standard Stories Column */}
        {(standardStories.length > 0 || otherStories.length > 0) && (
          <div className={`${compactStories.length > 0 ? "lg:col-span-8" : "lg:col-span-12"} flex flex-col divide-y divide-[#E8E1D5]`}>
            {[...standardStories, ...otherStories].map((story) => (
              <EditionStoryCard
                key={story.id}
                story={story}
                token={token}
                layout="STANDARD"
                onActionComplete={onActionComplete}
              />
            ))}
          </div>
        )}

        {/* Compact Stories Sidebar */}
        {compactStories.length > 0 && (
          <div className="lg:col-span-4 bg-[#F8F5EE] p-4 border border-[#E5DEC7] rounded-sm self-start">
            <h3 className="text-xs font-bold uppercase tracking-widest text-[#181615] pb-2 mb-3 border-b border-[#DCD3C7]">
              In Brief
            </h3>
            <div className="flex flex-col divide-y divide-[#E8E1D5]">
              {compactStories.map((story) => (
                <EditionStoryCard
                  key={story.id}
                  story={story}
                  token={token}
                  layout="COMPACT"
                  onActionComplete={onActionComplete}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
