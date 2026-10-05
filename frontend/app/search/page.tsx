"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import {
  Search as SearchIcon,
  SlidersHorizontal,
  Clock,
  BookOpen,
  Sparkles,
  History,
  Trash2,
  X,
  ChevronLeft,
  ChevronRight,
  Filter,
  ArrowRight,
  AlertCircle,
  TrendingUp,
} from "lucide-react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { AuthModal } from "@/components/AuthModal";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Onboarding } from "@/components/Onboarding";
import {
  searchArticles,
  fetchSearchSuggestions,
  fetchSearchHistory,
  clearSearchHistory,
  fetchCurrentUser,
} from "@/lib/api";
import {
  SearchResultItem,
  SearchResponse,
  SearchSuggestionItem,
  SearchHistoryItem,
  User,
} from "@/types";

const CATEGORIES = [
  "ALL",
  "TECHNOLOGY",
  "SCIENCE",
  "BUSINESS",
  "FINANCE",
  "WORLD",
  "POLITICS",
  "HEALTH",
  "SPORTS",
  "ENTERTAINMENT",
];

const DATE_PRESETS = [
  { label: "All Time", value: "" },
  { label: "Today", value: "today" },
  { label: "Yesterday", value: "yesterday" },
  { label: "Last 7 Days", value: "last_7_days" },
  { label: "Last 30 Days", value: "last_30_days" },
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("ALL");
  const [selectedDatePreset, setSelectedDatePreset] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("");

  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Suggestions & History
  const [suggestions, setSuggestions] = useState<SearchSuggestionItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // User & Modals
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [interestsModalOpen, setInterestsModalOpen] = useState(false);

  const searchContainerRef = useRef<HTMLDivElement>(null);

  // Initialize auth state
  useEffect(() => {
    const savedToken = localStorage.getItem("auth_token");
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser(savedToken)
        .then((u) => {
          setUser(u);
          loadSearchHistory(savedToken);
        })
        .catch(() => {
          localStorage.removeItem("auth_token");
          setToken(null);
          setUser(null);
        });
    }
  }, []);

  const loadSearchHistory = async (authToken: string) => {
    try {
      const res = await fetchSearchHistory(authToken, 10);
      setHistory(res.history);
    } catch (err) {
      console.warn("Could not load search history:", err);
    }
  };

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        searchContainerRef.current &&
        !searchContainerRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
        setShowHistory(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch Autocomplete Suggestions (debounced)
  useEffect(() => {
    if (!query.trim() || query.length < 2) {
      setSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const res = await fetchSearchSuggestions(query.trim(), 6);
        setSuggestions(res.suggestions);
      } catch {
        setSuggestions([]);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  // Execute Search
  const executeSearch = useCallback(
    async (searchPage: number = 1, customQuery?: string) => {
      const activeQuery = customQuery !== undefined ? customQuery : query;
      setLoading(true);
      setError(null);
      setShowSuggestions(false);
      setShowHistory(false);

      try {
        const res = await searchArticles(
          {
            q: activeQuery,
            category: selectedCategory !== "ALL" ? selectedCategory : undefined,
            date_preset: selectedDatePreset || undefined,
            source: selectedSource.trim() || undefined,
            topic: selectedTopic.trim() || undefined,
            page: searchPage,
            page_size: 15,
          },
          token || undefined
        );

        setSearchResponse(res);
        setPage(searchPage);

        if (token) {
          loadSearchHistory(token);
        }
      } catch (err: any) {
        setError(err.message || "An error occurred while executing search.");
      } finally {
        setLoading(false);
      }
    },
    [query, selectedCategory, selectedDatePreset, selectedSource, selectedTopic, token]
  );

  // Initial search on mount
  useEffect(() => {
    executeSearch(1, "");
  }, [executeSearch]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(1);
  };

  const handleSuggestionClick = (text: string) => {
    setQuery(text);
    executeSearch(1, text);
  };

  const handleClearHistory = async () => {
    if (!token) return;
    try {
      await clearSearchHistory(token);
      setHistory([]);
    } catch (err) {
      console.error("Failed to clear search history:", err);
    }
  };

  const handleResetFilters = () => {
    setSelectedCategory("ALL");
    setSelectedDatePreset("");
    setSelectedSource("");
    setSelectedTopic("");
    setQuery("");
    executeSearch(1, "");
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] text-[#121212] flex flex-col font-serif selection:bg-amber-100">
      <Header
        user={user}
        onOpenAuth={() => setAuthModalOpen(true)}
        onOpenOnboarding={() => setOnboardingOpen(true)}
        onOpenInterests={() => setInterestsModalOpen(true)}
        onSignOut={() => {
          localStorage.removeItem("auth_token");
          setToken(null);
          setUser(null);
          setHistory([]);
        }}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-8 py-8">
        {/* Broadsheet Search Masthead Banner */}
        <div className="border-b-4 border-double border-[#121212] pb-6 mb-8 text-center">
          <span className="text-[11px] font-sans font-bold uppercase tracking-[0.25em] text-red-800">
            Intelligent News Archive & Vector Engine
          </span>
          <h2 className="text-3xl sm:text-5xl font-bold tracking-tight uppercase mt-1 mb-2 font-serif">
            Newspaper Search & Discovery
          </h2>
          <p className="text-sm italic text-stone-600 max-w-2xl mx-auto font-serif">
            Query articles using full-text keyword weighting, semantic vector understanding,
            and personalized relevance ranking.
          </p>
        </div>

        {/* Search Bar Container */}
        <div ref={searchContainerRef} className="relative max-w-3xl mx-auto mb-6">
          <form onSubmit={handleSearchSubmit} className="relative flex items-center">
            <div className="relative w-full flex items-center">
              <input
                id="search-input"
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                placeholder="Search articles by keywords, topics, entities (e.g. OpenAI this week, AI research)..."
                className="w-full pl-12 pr-28 py-3.5 bg-white border-2 border-[#121212] rounded-none text-base font-sans focus:outline-none focus:ring-2 focus:ring-red-700 shadow-sm"
              />
              <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-stone-500" />
              {query && (
                <button
                  type="button"
                  onClick={() => {
                    setQuery("");
                    executeSearch(1, "");
                  }}
                  className="absolute right-28 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-700"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              <button
                id="search-submit-button"
                type="submit"
                className="absolute right-1.5 top-1.5 bottom-1.5 px-5 bg-[#121212] text-white font-sans text-xs font-bold uppercase tracking-wider hover:bg-red-800 transition-colors"
              >
                Search
              </button>
            </div>
          </form>

          {/* Autocomplete Suggestions Dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute left-0 right-0 top-full mt-1 bg-white border-2 border-[#121212] shadow-xl z-30 font-sans divide-y divide-stone-100">
              <div className="px-3 py-1.5 bg-stone-50 text-[10px] uppercase tracking-wider font-bold text-stone-500 flex justify-between items-center">
                <span>Suggestions</span>
                <Sparkles className="w-3 h-3 text-amber-600" />
              </div>
              {suggestions.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSuggestionClick(s.text)}
                  className="w-full text-left px-4 py-2.5 hover:bg-amber-50 flex items-center justify-between text-sm transition-colors"
                >
                  <span className="font-medium text-stone-900">{s.text}</span>
                  <span className="text-[11px] uppercase tracking-wider text-stone-500 bg-stone-100 px-2 py-0.5 rounded">
                    {s.subtitle || s.type}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Filters Bar */}
        <div className="bg-stone-100 border border-stone-300 p-4 mb-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-1.5 text-xs font-sans font-bold uppercase tracking-wider text-stone-700">
                <SlidersHorizontal className="w-3.5 h-3.5" /> Filters:
              </span>

              {/* Category Filter */}
              <select
                id="category-filter"
                value={selectedCategory}
                onChange={(e) => {
                  setSelectedCategory(e.target.value);
                  setPage(1);
                }}
                className="bg-white border border-stone-300 text-xs font-sans font-medium px-2.5 py-1.5 rounded focus:ring-1 focus:ring-stone-900"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat === "ALL" ? "All Categories" : cat}
                  </option>
                ))}
              </select>

              {/* Date Preset Filter */}
              <select
                id="date-filter"
                value={selectedDatePreset}
                onChange={(e) => {
                  setSelectedDatePreset(e.target.value);
                  setPage(1);
                }}
                className="bg-white border border-stone-300 text-xs font-sans font-medium px-2.5 py-1.5 rounded focus:ring-1 focus:ring-stone-900"
              >
                {DATE_PRESETS.map((dp) => (
                  <option key={dp.value} value={dp.value}>
                    {dp.label}
                  </option>
                ))}
              </select>

              {/* Source Input Filter */}
              <input
                id="source-filter"
                type="text"
                placeholder="Source (e.g. Reuters)"
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
                className="bg-white border border-stone-300 text-xs font-sans font-medium px-2.5 py-1.5 rounded w-36 focus:ring-1 focus:ring-stone-900"
              />

              <button
                type="button"
                onClick={() => executeSearch(1)}
                className="px-3 py-1.5 bg-stone-900 text-white text-xs font-sans font-bold uppercase rounded hover:bg-stone-800 transition-colors"
              >
                Apply Filters
              </button>
            </div>

            <div className="flex items-center gap-2">
              {/* Reset Filters */}
              {(selectedCategory !== "ALL" ||
                selectedDatePreset ||
                selectedSource ||
                query) && (
                <button
                  type="button"
                  onClick={handleResetFilters}
                  className="text-xs font-sans text-red-700 hover:text-red-900 font-semibold underline"
                >
                  Reset All
                </button>
              )}

              {/* Search History Toggle (if authenticated) */}
              {token && history.length > 0 && (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowHistory(!showHistory)}
                    className="flex items-center gap-1 text-xs font-sans text-stone-700 hover:text-stone-900 bg-white border border-stone-300 px-2.5 py-1.5 rounded"
                  >
                    <History className="w-3.5 h-3.5" /> Recent Searches
                  </button>

                  {showHistory && (
                    <div className="absolute right-0 top-full mt-2 w-72 bg-white border border-stone-300 shadow-xl z-20 font-sans p-3">
                      <div className="flex items-center justify-between border-b border-stone-200 pb-2 mb-2">
                        <span className="text-xs font-bold uppercase text-stone-600">
                          Search History
                        </span>
                        <button
                          type="button"
                          onClick={handleClearHistory}
                          className="text-[11px] text-red-600 hover:text-red-800 flex items-center gap-1"
                        >
                          <Trash2 className="w-3 h-3" /> Clear
                        </button>
                      </div>
                      <div className="space-y-1.5 max-h-60 overflow-y-auto">
                        {history.map((h) => (
                          <button
                            key={h.id}
                            type="button"
                            onClick={() => {
                              setQuery(h.query);
                              executeSearch(1, h.query);
                            }}
                            className="w-full text-left text-xs py-1 px-1.5 hover:bg-stone-100 rounded text-stone-800 flex justify-between items-center"
                          >
                            <span className="truncate">{h.query}</span>
                            <span className="text-[10px] text-stone-400 shrink-0 ml-2">
                              {h.result_count} results
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Search Feedback & Results Count Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-stone-300 pb-2 mb-6 text-xs font-sans text-stone-600">
          <div>
            {searchResponse && (
              <span>
                Found{" "}
                <strong className="text-stone-900 font-bold">
                  {searchResponse.total_results}
                </strong>{" "}
                articles in {searchResponse.execution_time_ms} ms
                {searchResponse.parsed_query?.date_range_detected && (
                  <span className="ml-2 bg-stone-200 px-1.5 py-0.5 rounded text-[11px]">
                    Date: {searchResponse.parsed_query.date_range_detected}
                  </span>
                )}
              </span>
            )}
          </div>
          {searchResponse?.parsed_query && (
            <div className="flex flex-wrap gap-1.5 mt-2 sm:mt-0">
              {searchResponse.parsed_query.detected_topics.map((top, idx) => (
                <span
                  key={idx}
                  className="bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded text-[11px] font-medium"
                >
                  Topic: {top}
                </span>
              ))}
              {searchResponse.parsed_query.detected_entities.map((ent, idx) => (
                <span
                  key={idx}
                  className="bg-blue-50 text-blue-800 border border-blue-200 px-2 py-0.5 rounded text-[11px] font-medium"
                >
                  Entity: {ent}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="py-16 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-stone-300 border-t-stone-900 mb-4" />
            <p className="text-sm font-sans text-stone-600">
              Searching full-text archives and running semantic vector matching...
            </p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="my-8 p-6 bg-red-50 border-l-4 border-red-700 text-red-900">
            <div className="flex items-center gap-2 mb-2 font-bold font-sans">
              <AlertCircle className="w-5 h-5 text-red-700" />
              Search Error
            </div>
            <p className="text-sm font-sans">{error}</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && searchResponse && searchResponse.results.length === 0 && (
          <div className="my-12 p-8 bg-stone-50 border border-stone-300 text-center max-w-xl mx-auto">
            <h3 className="text-xl font-bold font-serif uppercase tracking-tight text-stone-900 mb-2">
              No Articles Found
            </h3>
            <p className="text-sm font-serif italic text-stone-600 mb-6">
              We couldn&apos;t find any articles matching your search terms and filters.
            </p>
            <div className="text-left bg-white p-4 border border-stone-200 text-xs font-sans space-y-2 text-stone-700">
              <strong className="block font-bold text-stone-900 uppercase">
                Suggestions:
              </strong>
              <ul className="list-disc pl-5 space-y-1">
                <li>Check for spelling errors or try alternative keywords.</li>
                <li>Remove active category or source filters.</li>
                <li>Broaden the date range filter to &ldquo;All Time&rdquo;.</li>
                <li>Try searching general topics like &ldquo;AI&rdquo;, &ldquo;Science&rdquo;, or &ldquo;Finance&rdquo;.</li>
              </ul>
            </div>
            <button
              type="button"
              onClick={handleResetFilters}
              className="mt-6 px-4 py-2 bg-[#121212] text-white text-xs font-sans font-bold uppercase tracking-wider hover:bg-stone-800 transition-colors"
            >
              Reset Search & Filters
            </button>
          </div>
        )}

        {/* Search Results List */}
        {!loading && searchResponse && searchResponse.results.length > 0 && (
          <div className="divide-y divide-stone-300">
            {searchResponse.results.map((item) => (
              <article
                key={item.article_id}
                className="py-6 hover:bg-amber-50/50 transition-colors px-3 sm:px-4"
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="flex-1">
                    {/* Metadata Header */}
                    <div className="flex flex-wrap items-center gap-2 text-xs font-sans text-stone-600 mb-1.5">
                      {item.primary_category && (
                        <span className="font-bold text-red-800 uppercase tracking-wider">
                          {item.primary_category}
                        </span>
                      )}
                      <span>•</span>
                      <span>{item.source_name || "Independent Source"}</span>
                      {item.published_at && (
                        <>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(item.published_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })}
                          </span>
                        </>
                      )}
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <BookOpen className="w-3 h-3" />
                        {item.reading_time_minutes} min read
                      </span>

                      {/* Match Explanation Badge */}
                      {item.match_explanation && (
                        <span className="ml-auto bg-amber-100 text-amber-900 border border-amber-300 text-[11px] font-sans font-semibold px-2 py-0.5 rounded-full flex items-center gap-1">
                          <Sparkles className="w-3 h-3 text-amber-700" />
                          {item.match_explanation}
                        </span>
                      )}
                    </div>

                    {/* Headline Linking to Existing Reader */}
                    <h3 className="text-xl sm:text-2xl font-bold font-serif leading-snug text-[#121212] mb-2 hover:text-red-800 transition-colors">
                      <Link href={`/article/${item.article_id}`}>
                        {item.title}
                      </Link>
                    </h3>

                    {/* Summary */}
                    {item.summary && (
                      <p className="text-sm font-serif text-stone-700 leading-relaxed line-clamp-3 mb-3">
                        {item.summary}
                      </p>
                    )}

                    {/* Topics & Entities Tags */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      {item.topics.slice(0, 3).map((topicName, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            setQuery(topicName);
                            executeSearch(1, topicName);
                          }}
                          className="text-[11px] font-sans bg-stone-100 hover:bg-stone-200 text-stone-700 px-2 py-0.5 rounded transition-colors"
                        >
                          #{topicName}
                        </button>
                      ))}
                      <Link
                        href={`/article/${item.article_id}`}
                        className="ml-auto inline-flex items-center gap-1 text-xs font-sans font-bold uppercase text-red-800 hover:text-red-950 transition-colors"
                      >
                        Read Full Article <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>

                  {/* Thumbnail Image if available */}
                  {item.top_image_url && (
                    <div className="md:w-48 shrink-0">
                      <Link href={`/article/${item.article_id}`}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={item.top_image_url}
                          alt={item.title}
                          className="w-full h-32 object-cover border border-stone-300 hover:opacity-90 transition-opacity"
                        />
                      </Link>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}

        {/* Pagination Controls */}
        {!loading && searchResponse && searchResponse.total_pages > 1 && (
          <div className="flex items-center justify-between border-t-2 border-[#121212] pt-6 mt-8 font-sans text-xs font-bold uppercase">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => executeSearch(page - 1)}
              className="flex items-center gap-1.5 px-4 py-2 border border-stone-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-stone-100 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" /> Previous
            </button>

            <span className="text-stone-700">
              Page {searchResponse.page} of {searchResponse.total_pages}
            </span>

            <button
              type="button"
              disabled={page >= searchResponse.total_pages}
              onClick={() => executeSearch(page + 1)}
              className="flex items-center gap-1.5 px-4 py-2 border border-stone-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-stone-100 transition-colors"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </main>

      <Footer />

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onAuthSuccess={(newToken, newUser) => {
          setToken(newToken);
          setUser(newUser);
          setAuthModalOpen(false);
          loadSearchHistory(newToken);
        }}
      />

      {/* Onboarding Modal */}
      {token && onboardingOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="relative w-full max-w-4xl">
            <button
              onClick={() => setOnboardingOpen(false)}
              className="absolute top-4 right-4 z-10 text-[#121212] hover:opacity-75"
            >
              <X className="w-5 h-5" />
            </button>
            <Onboarding
              token={token}
              onComplete={() => {
                setOnboardingOpen(false);
                executeSearch(1);
              }}
            />
          </div>
        </div>
      )}

      {/* Interests Management Modal */}
      {token && (
        <MyInterestsModal
          isOpen={interestsModalOpen}
          token={token}
          onClose={() => {
            setInterestsModalOpen(false);
            executeSearch(1);
          }}
        />
      )}
    </div>
  );
}
