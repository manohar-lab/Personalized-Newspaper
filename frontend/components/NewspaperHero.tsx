"use client";

import React from "react";
import { ArrowRight, Sparkles, Newspaper as NewspaperIcon } from "lucide-react";

export function NewspaperHero() {
  return (
    <section className="my-8 max-w-7xl mx-auto px-4 sm:px-8">
      <div className="bg-paper-100 border border-paper-300 rounded-sm p-6 sm:p-10 shadow-sm relative overflow-hidden">
        {/* Newspaper subtle background lines */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-accent-sepia/5 rounded-full blur-3xl -z-0"></div>

        <div className="relative z-10 grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
          {/* Main Lead Column */}
          <div className="md:col-span-8 space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-paper-200 border border-paper-300 rounded-full text-xs font-serif italic text-ink">
              <Sparkles className="h-3.5 w-3.5 text-accent-red" />
              AI-Curated Intelligence & Web Ingestion Engine
            </div>

            <h2 className="font-serif text-3xl sm:text-5xl font-bold tracking-tight text-ink leading-tight">
              A daily paper written exclusively for your curiosity.
            </h2>

            <p className="font-sans text-base sm:text-lg text-gray-700 leading-relaxed max-w-2xl">
              We ingest stories across permitted web sources and RSS feeds, run real-time AI classification, and rank every article according to your evolving preferences.
            </p>

            <div className="pt-4 flex flex-wrap items-center gap-4">
              <a
                href="#get-started"
                className="inline-flex items-center space-x-2 bg-accent-red hover:bg-red-900 text-white font-sans font-semibold px-6 py-3 rounded text-sm transition-all shadow-md hover:shadow-lg"
              >
                <span>Get Started</span>
                <ArrowRight className="h-4 w-4" />
              </a>

              <a
                href="#browse"
                className="inline-flex items-center space-x-2 bg-white hover:bg-paper-50 text-ink border border-paper-300 font-sans font-semibold px-6 py-3 rounded text-sm transition-all shadow-sm hover:border-gray-400"
              >
                <NewspaperIcon className="h-4 w-4 text-gray-600" />
                <span>Browse Newspaper</span>
              </a>
            </div>
          </div>

          {/* Side Editorial Box */}
          <div className="md:col-span-4 border-l-0 md:border-l border-paper-300 pl-0 md:pl-8 space-y-4">
            <div className="border-b border-ink pb-2">
              <span className="font-serif font-bold text-xs uppercase tracking-widest text-accent-red">
                Core Promise
              </span>
              <h3 className="font-serif font-semibold text-lg text-ink mt-1">
                Zero Clickbait. Full Attribution.
              </h3>
            </div>
            
            <ul className="space-y-3 font-sans text-xs text-gray-600">
              <li className="flex items-start gap-2">
                <span className="font-serif font-bold text-ink text-sm">1.</span>
                <span>Full-text rendering when licensed, direct source links when original publisher site is required.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-serif font-bold text-ink text-sm">2.</span>
                <span>Adaptive recommendation algorithm that learns from your likes, saves, and reading duration.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="font-serif font-bold text-ink text-sm">3.</span>
                <span>Instant topic silencing when you mark "Not interested".</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
