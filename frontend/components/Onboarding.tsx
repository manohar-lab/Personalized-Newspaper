"use client";

import React, { useEffect, useState } from "react";
import { Topic, UserInterest } from "@/types";
import { fetchTopics, submitOnboardingInterests, fetchMyInterests } from "@/lib/api";
import { Check, Minus, Sparkles, ArrowRight, AlertCircle, CheckCircle2 } from "lucide-react";

interface OnboardingProps {
  token: string;
  onComplete: () => void;
}

export const Onboarding: React.FC<OnboardingProps> = ({ token, onComplete }) => {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [positiveSlugs, setPositiveSlugs] = useState<string[]>([]);
  const [negativeSlugs, setNegativeSlugs] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [fetchedTopics, existingInterests] = await Promise.all([
          fetchTopics(),
          fetchMyInterests(token).catch(() => [] as UserInterest[]),
        ]);

        setTopics(fetchedTopics);

        if (existingInterests.length > 0) {
          const pos = existingInterests
            .filter((i) => i.preference_type === "POSITIVE")
            .map((i) => i.topic_slug);
          const neg = existingInterests
            .filter((i) => i.preference_type === "NEGATIVE")
            .map((i) => i.topic_slug);
          setPositiveSlugs(pos);
          setNegativeSlugs(neg);
        } else {
          // Pre-select default popular positive topics if fresh user
          const defaults = ["artificial-intelligence", "machine-learning", "programming", "startups"];
          const availableDefaults = defaults.filter((d) =>
            fetchedTopics.some((t) => t.slug === d)
          );
          setPositiveSlugs(availableDefaults);
        }
      } catch (err: any) {
        setError("Failed to load topics from backend API.");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [token]);

  const togglePositive = (slug: string) => {
    if (positiveSlugs.includes(slug)) {
      setPositiveSlugs(positiveSlugs.filter((s) => s !== slug));
    } else {
      setPositiveSlugs([...positiveSlugs, slug]);
      setNegativeSlugs(negativeSlugs.filter((s) => s !== slug));
    }
  };

  const toggleNegative = (slug: string) => {
    if (negativeSlugs.includes(slug)) {
      setNegativeSlugs(negativeSlugs.filter((s) => s !== slug));
    } else {
      setNegativeSlugs([...negativeSlugs, slug]);
      setPositiveSlugs(positiveSlugs.filter((s) => s !== slug));
    }
  };

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      setError(null);
      await submitOnboardingInterests(token, positiveSlugs, negativeSlugs);
      setSuccessMessage("Preferences saved successfully to PostgreSQL database!");
      setTimeout(() => {
        onComplete();
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to save onboarding preferences.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto my-12 p-8 text-center font-serif bg-[#FAF9F5] border border-[#D3CBB9]">
        <p className="text-lg text-[#121212] animate-pulse">
          Retrieving topic categories from PostgreSQL...
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto my-8 p-6 md:p-10 bg-[#FAF9F5] border-2 border-[#121212] shadow-[8px_8px_0px_0px_rgba(18,18,18,1)] font-serif">
      {/* Newspaper Header */}
      <div className="text-center border-b-4 border-double border-[#121212] pb-6 mb-8">
        <div className="flex items-center justify-center gap-2 text-xs font-sans tracking-widest uppercase text-[#8C8275] mb-2">
          <Sparkles className="w-4 h-4 text-[#8C8275]" />
          <span>Personalization Engine</span>
          <Sparkles className="w-4 h-4 text-[#8C8275]" />
        </div>
        <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tight text-[#121212]">
          WELCOME TO YOUR PERSONAL NEWSPAPER
        </h1>
        <p className="text-lg md:text-xl font-serif italic text-[#4A453E] mt-3">
          &ldquo;Tell us what you want to read.&rdquo;
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-300 text-red-900 font-sans text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMessage && (
        <div className="mb-6 p-4 bg-emerald-50 border border-emerald-400 text-emerald-900 font-sans text-sm flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      <div className="space-y-10">
        {/* INTERESTED IN SECTION */}
        <section>
          <div className="flex items-center justify-between border-b border-[#121212] pb-2 mb-4">
            <h2 className="text-xl font-bold uppercase tracking-wider text-[#121212] flex items-center gap-2">
              <span className="w-3 h-3 bg-[#065F46] inline-block rounded-full"></span>
              INTERESTED IN
            </h2>
            <span className="text-xs font-sans text-[#8C8275] uppercase">
              {positiveSlugs.length} topics selected
            </span>
          </div>
          <p className="text-xs font-sans text-[#4A453E] mb-4">
            Select topics you want to see prioritized in your daily edition.
          </p>

          <div className="flex flex-wrap gap-2.5">
            {topics.map((topic) => {
              const isSelected = positiveSlugs.includes(topic.slug);
              return (
                <button
                  key={`pos-${topic.id}`}
                  type="button"
                  onClick={() => togglePositive(topic.slug)}
                  className={`px-3.5 py-2 text-sm font-sans font-medium transition-all flex items-center gap-2 border ${
                    isSelected
                      ? "bg-[#065F46] text-white border-[#065F46] shadow-sm font-semibold"
                      : "bg-[#F3EFE6] text-[#121212] border-[#D3CBB9] hover:border-[#121212] hover:bg-[#EAE4D5]"
                  }`}
                >
                  {isSelected && <Check className="w-4 h-4 shrink-0 stroke-[3]" />}
                  <span>{topic.name}</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* LESS INTERESTED IN SECTION */}
        <section className="pt-4">
          <div className="flex items-center justify-between border-b border-[#121212] pb-2 mb-4">
            <h2 className="text-xl font-bold uppercase tracking-wider text-[#121212] flex items-center gap-2">
              <span className="w-3 h-3 bg-[#991B1B] inline-block rounded-full"></span>
              LESS INTERESTED IN
            </h2>
            <span className="text-xs font-sans text-[#8C8275] uppercase">
              {negativeSlugs.length} topics filtered out
            </span>
          </div>
          <p className="text-xs font-sans text-[#4A453E] mb-4">
            Select topics you prefer to minimize or exclude.
          </p>

          <div className="flex flex-wrap gap-2.5">
            {topics.map((topic) => {
              const isSelected = negativeSlugs.includes(topic.slug);
              return (
                <button
                  key={`neg-${topic.id}`}
                  type="button"
                  onClick={() => toggleNegative(topic.slug)}
                  className={`px-3.5 py-2 text-sm font-sans font-medium transition-all flex items-center gap-2 border ${
                    isSelected
                      ? "bg-[#991B1B] text-white border-[#991B1B] shadow-sm font-semibold"
                      : "bg-[#F3EFE6] text-[#121212] border-[#D3CBB9] hover:border-[#121212] hover:bg-[#EAE4D5]"
                  }`}
                >
                  {isSelected && <Minus className="w-4 h-4 shrink-0 stroke-[3]" />}
                  <span>{topic.name}</span>
                </button>
              );
            })}
          </div>
        </section>
      </div>

      {/* FOOTER ACTION */}
      <div className="mt-10 pt-6 border-t-2 border-[#121212] flex flex-col sm:flex-row items-center justify-between gap-4 font-sans">
        <p className="text-xs text-[#8C8275]">
          Preferences will be saved to your profile and used by the Interest Agent.
        </p>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full sm:w-auto px-8 py-3 bg-[#121212] text-white font-sans text-sm font-bold uppercase tracking-wider hover:bg-[#2A2A2A] transition-colors flex items-center justify-center gap-2 border border-[#121212]"
        >
          <span>{submitting ? "Saving..." : "Continue →"}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
