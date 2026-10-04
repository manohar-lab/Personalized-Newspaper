"use client";

import React from "react";
import { Sparkles, Sliders, ArrowRight } from "lucide-react";

interface CurationBannerProps {
  userName?: string;
  curationSummary?: string;
  hasInterests?: boolean;
  onEditInterests?: () => void;
  onOpenOnboarding?: () => void;
}

export function CurationBanner({
  userName,
  curationSummary,
  hasInterests = true,
  onEditInterests,
  onOpenOnboarding,
}: CurationBannerProps) {
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  return (
    <section className="bg-[#F4EFE6] border-y border-[#DCD3C7] py-6 sm:py-8 px-4 sm:px-8 mb-8 font-sans">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="font-editorial-heading text-xl sm:text-2xl lg:text-3xl font-bold text-[#181615]">
            {getGreeting()}, {userName || "Reader"}.
          </h2>
          <p className="font-editorial-body text-sm sm:text-base text-[#5C554E] mt-1 max-w-3xl">
            {curationSummary || "Your personalized news edition for today."}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {hasInterests ? (
            onEditInterests && (
              <button
                onClick={onEditInterests}
                className="px-4 py-2 bg-white border border-[#181615] text-[#181615] text-xs font-bold uppercase tracking-wider hover:bg-[#181615] hover:text-[#FAF8F5] transition-colors flex items-center gap-1.5"
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Adjust Interests</span>
              </button>
            )
          ) : (
            onOpenOnboarding && (
              <button
                onClick={onOpenOnboarding}
                className="px-4 py-2 bg-[#8C2524] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#6D1B1B] transition-colors flex items-center gap-1.5 shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                <span>Set Your Interests</span>
              </button>
            )
          )}
        </div>
      </div>
    </section>
  );
}
