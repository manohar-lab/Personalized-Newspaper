"use client";

import React from "react";

export function NewspaperSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-8 animate-pulse font-sans">
      {/* Curation banner skeleton */}
      <div className="h-24 bg-[#EFE9DF] rounded-sm mb-10" />

      {/* Featured Lead Story skeleton */}
      <div className="border-2 border-[#DCD3C7] p-8 mb-12 bg-white/50">
        <div className="h-6 w-32 bg-[#E5DDD0] mb-6 rounded" />
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          <div className="lg:col-span-7 space-y-4">
            <div className="h-4 w-48 bg-[#E5DDD0] rounded" />
            <div className="h-10 w-full bg-[#DCD3C7] rounded" />
            <div className="h-10 w-3/4 bg-[#DCD3C7] rounded" />
            <div className="h-20 w-full bg-[#E5DDD0] rounded" />
            <div className="h-10 w-40 bg-[#181615]/20 rounded mt-6" />
          </div>
          <div className="lg:col-span-5 h-64 bg-[#E5DDD0] rounded" />
        </div>
      </div>

      {/* Section skeletons */}
      <div className="space-y-12">
        {[1, 2].map((n) => (
          <div key={n} className="border-t-2 border-[#DCD3C7] pt-6">
            <div className="h-8 w-60 bg-[#DCD3C7] mb-6 rounded" />
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-7 h-72 bg-[#E5DDD0] rounded" />
              <div className="lg:col-span-5 space-y-4">
                <div className="h-32 bg-[#E5DDD0] rounded" />
                <div className="h-32 bg-[#E5DDD0] rounded" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
