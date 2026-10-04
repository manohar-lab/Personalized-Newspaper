"use client";

import React from "react";
import { Sparkles, Newspaper, Sliders, RefreshCw } from "lucide-react";

interface EmptyNewspaperStateProps {
  type: "no_interests" | "no_articles" | "error";
  errorMessage?: string;
  onOpenOnboarding?: () => void;
  onRetry?: () => void;
}

export function EmptyNewspaperState({
  type,
  errorMessage,
  onOpenOnboarding,
  onRetry,
}: EmptyNewspaperStateProps) {
  if (type === "no_interests") {
    return (
      <div className="max-w-2xl mx-auto my-16 p-8 sm:p-12 text-center bg-white border-2 border-[#181615] shadow-sm font-sans">
        <div className="w-16 h-16 bg-[#F5EFEB] border border-[#DCD3C7] rounded-full flex items-center justify-center mx-auto mb-6 text-[#8C2524]">
          <Sparkles className="w-8 h-8" />
        </div>

        <h2 className="font-editorial-heading text-2xl sm:text-3xl font-bold text-[#181615] mb-3">
          Your newspaper isn't personalized yet.
        </h2>

        <p className="font-editorial-body text-base text-[#5C554E] max-w-lg mx-auto mb-8 leading-relaxed">
          Select the topics you care about most (and filter out what you don't) to generate your custom daily digital edition.
        </p>

        {onOpenOnboarding && (
          <button
            onClick={onOpenOnboarding}
            className="px-6 py-3 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors inline-flex items-center gap-2 shadow-sm"
          >
            <Sliders className="w-4 h-4 text-amber-300" />
            <span>Set your interests</span>
          </button>
        )}
      </div>
    );
  }

  if (type === "no_articles") {
    return (
      <div className="max-w-2xl mx-auto my-16 p-8 sm:p-12 text-center bg-white border border-[#DCD3C7] font-sans">
        <div className="w-16 h-16 bg-[#F5EFEB] rounded-full flex items-center justify-center mx-auto mb-6 text-[#5C554E]">
          <Newspaper className="w-8 h-8" />
        </div>

        <h2 className="font-editorial-heading text-2xl font-bold text-[#181615] mb-3">
          Your newspaper is waiting for today's stories.
        </h2>

        <p className="font-editorial-body text-base text-[#5C554E] max-w-md mx-auto mb-6">
          No published articles matched your selected criteria at this moment. Check back soon for the next editorial dispatch.
        </p>

        {onRetry && (
          <button
            onClick={onRetry}
            className="px-5 py-2.5 bg-white border border-[#181615] text-[#181615] text-xs font-bold uppercase tracking-wider hover:bg-[#F5EFEB] transition-colors inline-flex items-center gap-2"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Edition</span>
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto my-16 p-8 text-center bg-rose-50 border border-rose-300 font-sans">
      <h3 className="text-lg font-bold text-rose-900 mb-2">Unable to load edition</h3>
      <p className="text-sm text-rose-700 mb-6">{errorMessage || "An unexpected error occurred."}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-rose-900 text-white text-xs font-bold uppercase tracking-wider hover:bg-rose-800 transition-colors inline-flex items-center gap-2"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Try Again</span>
        </button>
      )}
    </div>
  );
}
