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
  Tag,
  Building,
  Layers,
  FileText,
  Check,
  Plus,
  VolumeX,
  ExternalLink,
  Calendar,
} from "lucide-react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
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
  SearchStoryItem,
  SearchTopicItem,
  SearchEntityItem,
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
  { label: "Last 24 Hours", value: "last_24_hours" },
  { label: "Last 7 Days", value: "last_7_days" },
  { label: "Last 30 Days", value: "last_30_days" },
  { label: "Custom Range", value: "custom" },
];

const SORT_OPTIONS = [
  { label: "Most Relevant", value: "relevance" },
  { label: "Newest First", value: "newest" },
  { label: "Most Important", value: "importance" },
];

const QUICK_SEARCH_EXAMPLES = [
  "AI agents",
  "NVIDIA",
  "Quantum computing",
  "OpenAI",
  "Machine learning",
  "Clean energy",
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("ALL");
  const [selectedDatePreset, setSelectedDatePreset] = useState("");
  const [customDateFrom, setCustomDateFrom] = useState("");
  const [customDateTo, setCustomDateTo] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("");
  const [sortBy, setSortBy] = useState("relevance");
  const [readStatus, setReadStatus] = useState("all");
  const [savedStatus, setSavedStatus] = useState("all");
  const [activeTab, setActiveTab] = useState<"ALL" | "STORIES" | "ARTICLES" | "TOPICS" | "ENTITIES">("ALL");
  const [deduplicate, setDeduplicate] = useState(true);

  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [showFiltersDrawer, setShowFiltersDrawer] = useState(false);

  // Suggestions & History
  const [suggestions, setSuggestions] = useState<SearchSuggestionItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [history, setHistory] = useState<SearchHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Local followed topic IDs
  const [followedTopicIds, setFollowedTopicIds] = useState<Set<string>>(new Set());

  // User & Modals
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [interestsModalOpen, setInterestsModalOpen] = useState(false);

  const searchContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Initialize auth state
  useEffect(() => {
    const savedToken = localStorage.getItem("auth_token") || localStorage.getItem("token");
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser(savedToken)
        .then((u) => {
          setUser(u);
          loadSearchHistory(savedToken);
        })
        .catch(() => {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("token");
          setToken(null);
          setUser(null);
        });
    }
  }, []);

  const loadSearchHistory = async (authToken: string) => {
    try {
      const res = await fetchSearchHistory(authToken, 10);
      setHistory(res.history || (res as any).recent || []);
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
        const res = await fetchSearchSuggestions(query.trim(), 8, token || undefined);
        setSuggestions(res.suggestions || []);
      } catch {
        setSuggestions([]);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, token]);

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
            date_preset: selectedDatePreset !== "custom" ? (selectedDatePreset || undefined) : undefined,
            date_from: selectedDatePreset === "custom" && customDateFrom ? new Date(customDateFrom).toISOString() : undefined,
            date_to: selectedDatePreset === "custom" && customDateTo ? new Date(customDateTo).toISOString() : undefined,
            source: selectedSource.trim() || undefined,
            topic: selectedTopic.trim() || undefined,
            sort_by: sortBy,
            read_status: token && readStatus !== "all" ? readStatus : undefined,
            saved_status: token && savedStatus !== "all" ? savedStatus : undefined,
            result_type: activeTab,
            deduplicate: deduplicate,
            page: searchPage,
            page_size: 15,
          },
          token || undefined
        );

        setSearchResponse(res);
        setPage(searchPage);

        // Pre-populate followed topic states
        if (res.topics) {
          const followed = new Set<string>();
          res.topics.forEach((t) => {
            if (t.is_followed) followed.add(t.id);
          });
          setFollowedTopicIds(followed);
        }

        if (token) {
          loadSearchHistory(token);
        }
      } catch (err: any) {
        setError(err.message || "An error occurred while executing search.");
      } finally {
        setLoading(false);
      }
    },
    [
      query,
      selectedCategory,
      selectedDatePreset,
      customDateFrom,
      customDateTo,
      selectedSource,
      selectedTopic,
      sortBy,
      readStatus,
      savedStatus,
      activeTab,
      deduplicate,
      token,
    ]
  );

  // Initial search on mount
  useEffect(() => {
    executeSearch(1, "");
  }, [executeSearch]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(1);
  };

  const handleClearQuery = () => {
    setQuery("");
    if (inputRef.current) inputRef.current.focus();
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
      setShowHistory(false);
    } catch (err) {
      console.error("Failed to clear search history:", err);
    }
  };

  const handleToggleTopicFollow = async (topic: SearchTopicItem) => {
    const isCurrentlyFollowed = followedTopicIds.has(topic.id);
    const updated = new Set(followedTopicIds);
    if (isCurrentlyFollowed) {
      updated.delete(topic.id);
    } else {
      updated.add(topic.id);
    }
    setFollowedTopicIds(updated);

    if (!token) return;

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      await fetch(`${API_BASE_URL}/api/interests`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          topic_slug: topic.slug,
          preference_type: isCurrentlyFollowed ? "NEGATIVE" : "POSITIVE",
          interest_score: isCurrentlyFollowed ? 0.0 : 1.0,
        }),
      });
    } catch (err) {
      console.warn("Error updating topic follow:", err);
    }
  };

  const handleResetFilters = () => {
    setSelectedCategory("ALL");
    setSelectedDatePreset("");
    setCustomDateFrom("");
    setCustomDateTo("");
    setSelectedSource("");
    setSelectedTopic("");
    setSortBy("relevance");
    setReadStatus("all");
    setSavedStatus("all");
    setActiveTab("ALL");
    setDeduplicate(true);
    setQuery("");
    executeSearch(1, "");
  };

  const storiesCount = searchResponse?.stories?.length || 0;
  const articlesCount = searchResponse?.articles?.length || searchResponse?.results?.length || 0;
  const topicsCount = searchResponse?.topics?.length || 0;
  const entitiesCount = searchResponse?.entities?.length || 0;

  return (
    <div className="min-h-screen bg-[#FDFBF7] text-[#121212] flex flex-col font-serif selection:bg-amber-100">
      <Header
        user={user}
        onOpenAuth={() => {}}
        onOpenOnboarding={() => setOnboardingOpen(true)}
        onOpenInterests={() => setInterestsModalOpen(true)}
        onSignOut={() => {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("token");
          setToken(null);
          setUser(null);
          setHistory([]);
        }}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-8 py-8">
        {/* Prominent Editorial Search Masthead */}
        <div className="border-b-4 border-double border-[#121212] pb-6 mb-8 text-center">
          <span className="text-[11px] font-sans font-bold uppercase tracking-[0.25em] text-red-800">
            Intelligent News Discovery Engine
          </span>
          <h1 className="text-3xl sm:text-5xl font-bold tracking-tight uppercase mt-1 mb-2 font-serif text-[#121212]">
            Search Your News
          </h1>
          <p className="text-base sm:text-lg italic text-stone-600 max-w-2xl mx-auto font-serif">
            &ldquo;What would you like to know about?&rdquo;
          </p>

          {/* Quick Search Tag Suggestions */}
          <div className="flex flex-wrap items-center justify-center gap-2 mt-4 font-sans text-xs">
            <span className="text-stone-500 font-medium">Try searching:</span>
            {QUICK_SEARCH_EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setQuery(example);
                  executeSearch(1, example);
                }}
                className="bg-stone-100 hover:bg-stone-200 text-stone-800 border border-stone-300 px-2.5 py-1 rounded transition-colors"
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* Prominent Search Bar Component */}
        <div className="mb-8" ref={searchContainerRef}>
          <form onSubmit={handleSearchSubmit} className="relative flex items-center">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-stone-400">
                <SearchIcon className="w-5 h-5" />
              </div>
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShowSuggestions(true);
                }}
                onFocus={() => {
                  if (query.trim().length >= 2) setShowSuggestions(true);
                }}
                placeholder="Search topics, companies, people, events, headlines, or publishers..."
                className="w-full pl-12 pr-12 py-3.5 bg-white border-2 border-stone-800 rounded-none text-base font-sans text-stone-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-900 shadow-sm"
              />
              {/* Clear Query Button */}
              {query && (
                <button
                  type="button"
                  onClick={handleClearQuery}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-stone-400 hover:text-stone-700"
                  title="Clear search query"
                  aria-label="Clear query"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="ml-3 px-6 py-3.5 bg-stone-900 hover:bg-stone-800 text-white font-sans font-bold text-sm uppercase tracking-wider transition-colors shrink-0 disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <SearchIcon className="w-4 h-4" />
              )}
              <span>Search</span>
            </button>

            {/* Filter Toggle Button */}
            <button
              type="button"
              onClick={() => setShowFiltersDrawer(!showFiltersDrawer)}
              className={`ml-2 px-3.5 py-3.5 border border-stone-300 font-sans text-sm transition-colors flex items-center gap-1.5 ${
                showFiltersDrawer ? "bg-stone-900 text-white" : "bg-white text-stone-700 hover:bg-stone-100"
              }`}
              title="Toggle filters"
            >
              <SlidersHorizontal className="w-4 h-4" />
              <span className="hidden sm:inline">Filters</span>
            </button>

            {/* Recent Searches Trigger (if authenticated) */}
            {token && history.length > 0 && (
              <button
                type="button"
                onClick={() => setShowHistory(!showHistory)}
                className="ml-2 px-3 py-3.5 bg-white border border-stone-300 text-stone-700 hover:bg-stone-100 font-sans text-sm transition-colors flex items-center gap-1"
                title="Recent searches"
              >
                <History className="w-4 h-4" />
              </button>
            )}
          </form>

          {/* Autocomplete Suggestions Dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="absolute left-0 right-0 max-w-4xl mt-1 bg-white border border-stone-300 shadow-2xl z-30 font-sans divide-y divide-stone-100">
              <div className="px-3 py-1.5 bg-stone-50 text-[11px] font-bold uppercase tracking-wider text-stone-500">
                Suggestions
              </div>
              {suggestions.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSuggestionClick(item.text)}
                  className="w-full text-left px-4 py-2.5 hover:bg-stone-100 flex items-center justify-between text-sm text-stone-800 transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    {item.type === "TOPIC" && <Tag className="w-3.5 h-3.5 text-emerald-600" />}
                    {item.type === "ENTITY" && <Building className="w-3.5 h-3.5 text-blue-600" />}
                    {item.type === "STORY" && <Layers className="w-3.5 h-3.5 text-purple-600" />}
                    {item.type === "RECENT" && <History className="w-3.5 h-3.5 text-amber-600" />}
                    <span className="font-medium">{item.text}</span>
                  </div>
                  {item.subtitle && (
                    <span className="text-xs text-stone-400 capitalize">{item.subtitle}</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Recent Searches Drawer / Dropdown */}
          {showHistory && history.length > 0 && (
            <div className="absolute right-0 max-w-md w-full mt-1 bg-white border border-stone-300 shadow-2xl z-30 font-sans p-3">
              <div className="flex items-center justify-between border-b border-stone-200 pb-2 mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-stone-700 flex items-center gap-1.5">
                  <History className="w-3.5 h-3.5" /> Recent Searches
                </span>
                <button
                  type="button"
                  onClick={handleClearHistory}
                  className="text-xs text-red-600 hover:text-red-800 flex items-center gap-1 font-medium"
                >
                  <Trash2 className="w-3 h-3" /> Clear History
                </button>
              </div>
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {history.map((h) => (
                  <button
                    key={h.id}
                    type="button"
                    onClick={() => {
                      setQuery(h.query);
                      executeSearch(1, h.query);
                    }}
                    className="w-full text-left text-xs py-1.5 px-2 hover:bg-stone-100 rounded text-stone-800 flex justify-between items-center transition-colors"
                  >
                    <span className="truncate">{h.query}</span>
                    <span className="text-[11px] text-stone-400 shrink-0 ml-2">
                      {h.result_count} results
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Filters Drawer / Options */}
        {showFiltersDrawer && (
          <div className="mb-8 p-6 bg-white border border-stone-300 shadow-sm font-sans text-xs">
            <div className="flex items-center justify-between border-b border-stone-200 pb-3 mb-4">
              <span className="font-bold uppercase tracking-wider text-stone-800 flex items-center gap-1.5">
                <Filter className="w-4 h-4" /> Search Filters & Sorting
              </span>
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-stone-500 hover:text-stone-800 font-medium underline"
              >
                Reset All Filters
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              {/* Category Filter */}
              <div>
                <label className="block font-bold uppercase tracking-wider text-stone-700 mb-1">
                  Category
                </label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full p-2 bg-stone-50 border border-stone-300 rounded focus:ring-1 focus:ring-stone-900"
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              {/* Date Presets */}
              <div>
                <label className="block font-bold uppercase tracking-wider text-stone-700 mb-1">
                  Publication Date
                </label>
                <select
                  value={selectedDatePreset}
                  onChange={(e) => setSelectedDatePreset(e.target.value)}
                  className="w-full p-2 bg-stone-50 border border-stone-300 rounded focus:ring-1 focus:ring-stone-900"
                >
                  {DATE_PRESETS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Sort By */}
              <div>
                <label className="block font-bold uppercase tracking-wider text-stone-700 mb-1">
                  Sort Results By
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="w-full p-2 bg-stone-50 border border-stone-300 rounded focus:ring-1 focus:ring-stone-900"
                >
                  {SORT_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Source Filter */}
              <div>
                <label className="block font-bold uppercase tracking-wider text-stone-700 mb-1">
                  Publisher / Source
                </label>
                <input
                  type="text"
                  value={selectedSource}
                  onChange={(e) => setSelectedSource(e.target.value)}
                  placeholder="e.g. Reuters, BBC"
                  className="w-full p-2 bg-stone-50 border border-stone-300 rounded focus:ring-1 focus:ring-stone-900"
                />
              </div>

              {/* Authenticated Filters: Read Status */}
              {token && (
                <div>
                  <label className="block font-bold uppercase tracking-wider text-stone-700 mb-1">
                    Reading Status
                  </label>
                  <select
                    value={readStatus}
                    onChange={(e) => setReadStatus(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-300 rounded focus:ring-1 focus:ring-stone-900"
                  >
                    <option value="all">All Articles</option>
                    <option value="unread">Unread Only</option>
                    <option value="read">Already Read</option>
                  </select>
                </div>
              )}

              {/* Authenticated Filters: Saved Status */}
              {token && (
                <div>
                  <label className="block font-bold uppercase tracking-wider text-stone-700 mb-1">
                    Saved Status
                  </label>
                  <select
                    value={savedStatus}
                    onChange={(e) => setSavedStatus(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-300 rounded focus:ring-1 focus:ring-stone-900"
                  >
                    <option value="all">All Articles</option>
                    <option value="saved">Saved Only</option>
                    <option value="unsaved">Unsaved</option>
                  </select>
                </div>
              )}

              {/* Deduplication Toggle */}
              <div className="flex items-center gap-2 pt-6">
                <input
                  type="checkbox"
                  id="dedup-check"
                  checked={deduplicate}
                  onChange={(e) => setDeduplicate(e.target.checked)}
                  className="w-4 h-4 text-stone-900 border-stone-300 rounded focus:ring-stone-900"
                />
                <label htmlFor="dedup-check" className="font-medium text-stone-700 select-none">
                  Suppress duplicate coverage
                </label>
              </div>

              {/* Apply Filters Button */}
              <div className="flex items-end">
                <button
                  type="button"
                  onClick={() => executeSearch(1)}
                  className="w-full py-2 bg-stone-900 text-white font-bold uppercase tracking-wider rounded hover:bg-stone-800 transition-colors"
                >
                  Apply Filters
                </button>
              </div>
            </div>

            {/* Custom Date Range Picker */}
            {selectedDatePreset === "custom" && (
              <div className="mt-4 pt-4 border-t border-stone-200 grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-medium text-stone-700 mb-1">From Date</label>
                  <input
                    type="date"
                    value={customDateFrom}
                    onChange={(e) => setCustomDateFrom(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-300 rounded"
                  />
                </div>
                <div>
                  <label className="block font-medium text-stone-700 mb-1">To Date</label>
                  <input
                    type="date"
                    value={customDateTo}
                    onChange={(e) => setCustomDateTo(e.target.value)}
                    className="w-full p-2 bg-stone-50 border border-stone-300 rounded"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Results Type Navigation Tabs */}
        <div className="flex flex-wrap items-center gap-2 border-b-2 border-stone-300 pb-2 mb-6 font-sans text-xs">
          <button
            type="button"
            onClick={() => setActiveTab("ALL")}
            className={`px-3 py-1.5 font-bold uppercase tracking-wider rounded transition-colors ${
              activeTab === "ALL"
                ? "bg-stone-900 text-white"
                : "bg-white text-stone-700 hover:bg-stone-100 border border-stone-200"
            }`}
          >
            All Results
          </button>
          {storiesCount > 0 && (
            <button
              type="button"
              onClick={() => setActiveTab("STORIES")}
              className={`px-3 py-1.5 font-bold uppercase tracking-wider rounded transition-colors flex items-center gap-1.5 ${
                activeTab === "STORIES"
                  ? "bg-stone-900 text-white"
                  : "bg-white text-stone-700 hover:bg-stone-100 border border-stone-200"
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-purple-600" />
              Stories ({storiesCount})
            </button>
          )}
          {articlesCount > 0 && (
            <button
              type="button"
              onClick={() => setActiveTab("ARTICLES")}
              className={`px-3 py-1.5 font-bold uppercase tracking-wider rounded transition-colors flex items-center gap-1.5 ${
                activeTab === "ARTICLES"
                  ? "bg-stone-900 text-white"
                  : "bg-white text-stone-700 hover:bg-stone-100 border border-stone-200"
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-stone-600" />
              Articles ({articlesCount})
            </button>
          )}
          {topicsCount > 0 && (
            <button
              type="button"
              onClick={() => setActiveTab("TOPICS")}
              className={`px-3 py-1.5 font-bold uppercase tracking-wider rounded transition-colors flex items-center gap-1.5 ${
                activeTab === "TOPICS"
                  ? "bg-stone-900 text-white"
                  : "bg-white text-stone-700 hover:bg-stone-100 border border-stone-200"
              }`}
            >
              <Tag className="w-3.5 h-3.5 text-emerald-600" />
              Topics ({topicsCount})
            </button>
          )}
          {entitiesCount > 0 && (
            <button
              type="button"
              onClick={() => setActiveTab("ENTITIES")}
              className={`px-3 py-1.5 font-bold uppercase tracking-wider rounded transition-colors flex items-center gap-1.5 ${
                activeTab === "ENTITIES"
                  ? "bg-stone-900 text-white"
                  : "bg-white text-stone-700 hover:bg-stone-100 border border-stone-200"
              }`}
            >
              <Building className="w-3.5 h-3.5 text-blue-600" />
              Entities ({entitiesCount})
            </button>
          )}
        </div>

        {/* Search Metadata & Parsed Signals Bar */}
        {searchResponse && (
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center text-xs font-sans text-stone-500 mb-6 pb-2 border-b border-stone-200">
            <div>
              Retrieved results in{" "}
              <strong className="text-stone-800 font-semibold">{searchResponse.execution_time_ms} ms</strong>
              {searchResponse.parsed_query?.date_range_detected && (
                <span className="ml-2 bg-stone-100 text-stone-700 px-2 py-0.5 rounded">
                  Date preset: {searchResponse.parsed_query.date_range_detected}
                </span>
              )}
            </div>

            {/* Detected topic/entity tags */}
            {searchResponse.parsed_query && (
              <div className="flex flex-wrap gap-1.5 mt-2 sm:mt-0">
                {searchResponse.parsed_query.detected_topics.map((t, idx) => (
                  <span
                    key={idx}
                    className="bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded text-[11px] font-medium"
                  >
                    Topic: {t}
                  </span>
                ))}
                {searchResponse.parsed_query.detected_entities.map((e, idx) => (
                  <span
                    key={idx}
                    className="bg-blue-50 text-blue-800 border border-blue-200 px-2 py-0.5 rounded text-[11px] font-medium"
                  >
                    Entity: {e}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="py-20 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-stone-300 border-t-stone-900 mb-4" />
            <p className="text-sm font-sans text-stone-600">
              Searching archives across stories, articles, topics, and entities...
            </p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="my-8 p-6 bg-red-50 border-l-4 border-red-700 text-red-900 font-sans">
            <div className="flex items-center gap-2 mb-2 font-bold">
              <AlertCircle className="w-5 h-5 text-red-700" />
              Unable to Complete Search
            </div>
            <p className="text-sm mb-4">{error}</p>
            <button
              type="button"
              onClick={() => executeSearch(page)}
              className="px-4 py-1.5 bg-red-800 text-white text-xs font-bold uppercase tracking-wider rounded hover:bg-red-900 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading &&
          !error &&
          searchResponse &&
          storiesCount === 0 &&
          articlesCount === 0 &&
          topicsCount === 0 &&
          entitiesCount === 0 && (
            <div className="my-12 p-8 bg-white border border-stone-300 text-center max-w-xl mx-auto shadow-sm">
              <h2 className="text-2xl font-bold font-serif uppercase tracking-tight text-stone-900 mb-2">
                No Results Found
              </h2>
              <p className="text-sm font-serif italic text-stone-600 mb-6">
                We couldn&apos;t find any stories, articles, topics, or entities matching &ldquo;{query}&rdquo;.
              </p>
              <div className="text-left bg-stone-50 p-4 border border-stone-200 text-xs font-sans space-y-2 text-stone-700">
                <strong className="block font-bold text-stone-900 uppercase">
                  Suggestions to Broaden Your Search:
                </strong>
                <ul className="list-disc pl-5 space-y-1">
                  <li>Check for spelling errors or try alternate terms.</li>
                  <li>Broaden your date range filter to &ldquo;All Time&rdquo;.</li>
                  <li>Clear category, publisher, or read/unread filters.</li>
                  <li>
                    Try popular topics like &ldquo;AI agents&rdquo;, &ldquo;Robotics&rdquo;, or &ldquo;NVIDIA&rdquo;.
                  </li>
                </ul>
              </div>
              <button
                type="button"
                onClick={handleResetFilters}
                className="mt-6 px-5 py-2.5 bg-stone-900 text-white text-xs font-sans font-bold uppercase tracking-wider hover:bg-stone-800 transition-colors"
              >
                Reset Search & Filters
              </button>
            </div>
          )}

        {/* ------------------------------------------------------------------ */}
        {/* RESULT SECTIONS: Only displayed when matching records exist        */}
        {/* ------------------------------------------------------------------ */}
        {!loading && searchResponse && (
          <div className="space-y-12">
            {/* 1. STORIES SECTION */}
            {(activeTab === "ALL" || activeTab === "STORIES") && storiesCount > 0 && (
              <section className="bg-white p-6 border border-stone-300 shadow-sm">
                <div className="flex items-center justify-between border-b-2 border-stone-900 pb-2 mb-4">
                  <h2 className="text-xl font-bold font-serif uppercase tracking-tight flex items-center gap-2">
                    <Layers className="w-5 h-5 text-purple-700" />
                    Covered Stories ({storiesCount})
                  </h2>
                  <span className="text-xs font-sans text-stone-500">Multi-source event synthesis</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {searchResponse.stories.map((story) => (
                    <article
                      key={story.id}
                      className="p-4 bg-stone-50 border border-stone-200 hover:border-stone-400 transition-colors flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2 text-[11px] font-sans font-bold text-purple-800 uppercase tracking-wider mb-1.5">
                          {story.primary_topic_name && <span>{story.primary_topic_name}</span>}
                          <span>•</span>
                          <span className="text-stone-500 font-normal">
                            {story.article_count} articles covering
                          </span>
                        </div>
                        <h3 className="text-lg font-bold font-serif text-stone-900 hover:text-purple-900 mb-2 leading-snug">
                          <Link href={`/stories/${story.slug}`}>{story.title}</Link>
                        </h3>
                        {story.summary && (
                          <p className="text-xs font-serif text-stone-600 line-clamp-3 mb-3">
                            {story.summary}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center justify-between pt-3 border-t border-stone-200 text-xs font-sans">
                        <span className="text-stone-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {story.last_updated_at
                            ? new Date(story.last_updated_at).toLocaleDateString()
                            : "Recently updated"}
                        </span>
                        <Link
                          href={`/stories/${story.slug}`}
                          className="font-bold text-purple-700 hover:text-purple-900 flex items-center gap-1 uppercase tracking-wider text-[11px]"
                        >
                          Read Story <ArrowRight className="w-3 h-3" />
                        </Link>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}

            {/* 2. TOPICS SECTION */}
            {(activeTab === "ALL" || activeTab === "TOPICS") && topicsCount > 0 && (
              <section className="bg-white p-6 border border-stone-300 shadow-sm">
                <div className="flex items-center justify-between border-b-2 border-stone-900 pb-2 mb-4">
                  <h2 className="text-xl font-bold font-serif uppercase tracking-tight flex items-center gap-2">
                    <Tag className="w-5 h-5 text-emerald-700" />
                    Topics ({topicsCount})
                  </h2>
                  <span className="text-xs font-sans text-stone-500">Subject areas & technologies</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {searchResponse.topics.map((t) => {
                    const isFollowed = followedTopicIds.has(t.id);
                    return (
                      <div
                        key={t.id}
                        className="p-3.5 bg-stone-50 border border-stone-200 flex items-center justify-between"
                      >
                        <div>
                          <h3 className="font-bold font-sans text-stone-900 text-sm">{t.name}</h3>
                          {t.description && (
                            <p className="text-xs font-serif text-stone-500 line-clamp-1">
                              {t.description}
                            </p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleToggleTopicFollow(t)}
                          className={`px-2.5 py-1 text-xs font-sans font-bold uppercase tracking-wider rounded flex items-center gap-1 transition-colors ${
                            isFollowed
                              ? "bg-emerald-700 text-white"
                              : "bg-white border border-stone-300 text-stone-700 hover:bg-stone-100"
                          }`}
                        >
                          {isFollowed ? (
                            <>
                              <Check className="w-3 h-3" /> Following
                            </>
                          ) : (
                            <>
                              <Plus className="w-3 h-3" /> Follow
                            </>
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* 3. ENTITIES SECTION */}
            {(activeTab === "ALL" || activeTab === "ENTITIES") && entitiesCount > 0 && (
              <section className="bg-white p-6 border border-stone-300 shadow-sm">
                <div className="flex items-center justify-between border-b-2 border-stone-900 pb-2 mb-4">
                  <h2 className="text-xl font-bold font-serif uppercase tracking-tight flex items-center gap-2">
                    <Building className="w-5 h-5 text-blue-700" />
                    Recognized Entities ({entitiesCount})
                  </h2>
                  <span className="text-xs font-sans text-stone-500">
                    Companies, researchers, and public figures
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {searchResponse.entities.map((e) => (
                    <div
                      key={e.id}
                      className="p-3.5 bg-stone-50 border border-stone-200 flex items-center justify-between"
                    >
                      <div>
                        <div className="text-[10px] font-sans font-bold text-blue-700 uppercase tracking-wider">
                          {e.entity_type}
                        </div>
                        <h3 className="font-bold font-sans text-stone-900 text-sm">{e.name}</h3>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setQuery(e.name);
                          executeSearch(1, e.name);
                        }}
                        className="px-2 py-1 text-xs font-sans font-bold uppercase tracking-wider bg-white border border-stone-300 text-stone-700 hover:bg-stone-100 rounded"
                      >
                        Explore
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 4. ARTICLES SECTION */}
            {(activeTab === "ALL" || activeTab === "ARTICLES") && articlesCount > 0 && (
              <section className="bg-white p-6 border border-stone-300 shadow-sm">
                <div className="flex items-center justify-between border-b-2 border-stone-900 pb-2 mb-6">
                  <h2 className="text-xl font-bold font-serif uppercase tracking-tight flex items-center gap-2">
                    <FileText className="w-5 h-5 text-stone-800" />
                    Articles ({searchResponse.total_results || articlesCount})
                  </h2>
                  <span className="text-xs font-sans text-stone-500">
                    Page {searchResponse.page} of {searchResponse.total_pages}
                  </span>
                </div>

                <div className="divide-y divide-stone-200">
                  {searchResponse.articles.map((item) => (
                    <article
                      key={item.article_id}
                      className="py-6 hover:bg-amber-50/40 transition-colors px-2 rounded"
                    >
                      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                        <div className="flex-1">
                          {/* Metadata row */}
                          <div className="flex flex-wrap items-center gap-2 text-xs font-sans text-stone-500 mb-2">
                            {item.primary_category && (
                              <span className="font-bold text-red-800 uppercase tracking-wider">
                                {item.primary_category}
                              </span>
                            )}
                            <span>•</span>
                            <span className="font-semibold text-stone-800">
                              {item.source_name || "Independent Source"}
                            </span>
                            {item.author && (
                              <>
                                <span>•</span>
                                <span>By {item.author}</span>
                              </>
                            )}
                            {item.published_at && (
                              <>
                                <span>•</span>
                                <span>{new Date(item.published_at).toLocaleDateString()}</span>
                              </>
                            )}
                            <span>•</span>
                            <span className="flex items-center gap-1">
                              <BookOpen className="w-3 h-3" />
                              {item.reading_time_minutes} min read
                            </span>
                            {item.is_paywalled && (
                              <span className="bg-amber-100 text-amber-900 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase">
                                Paywalled
                              </span>
                            )}
                            {item.match_explanation && (
                              <span className="bg-stone-200 text-stone-800 px-1.5 py-0.5 rounded text-[10px] font-medium">
                                {item.match_explanation}
                              </span>
                            )}
                          </div>

                          {/* Headline */}
                          <h3 className="text-xl font-bold font-serif text-stone-900 hover:text-red-900 leading-snug mb-2">
                            <Link href={`/article/${item.article_id}`}>{item.title}</Link>
                          </h3>

                          {/* Summary */}
                          {item.summary && (
                            <p className="text-sm font-serif text-stone-700 leading-relaxed mb-3 line-clamp-3">
                              {item.summary}
                            </p>
                          )}

                          {/* Topic & Entity tags */}
                          <div className="flex flex-wrap items-center gap-1.5">
                            {item.topics.slice(0, 3).map((top, idx) => (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  setSelectedTopic(top);
                                  executeSearch(1);
                                }}
                                className="text-[11px] font-sans bg-stone-100 hover:bg-stone-200 text-stone-700 px-2 py-0.5 rounded"
                              >
                                #{top}
                              </button>
                            ))}
                            {item.entities.slice(0, 2).map((ent, idx) => (
                              <span
                                key={idx}
                                className="text-[11px] font-sans bg-blue-50 text-blue-700 px-2 py-0.5 rounded"
                              >
                                @{ent}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Thumbnail image if available */}
                        {item.top_image_url && (
                          <div className="md:w-44 md:h-28 w-full h-40 bg-stone-200 shrink-0 overflow-hidden rounded border border-stone-200">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={item.top_image_url}
                              alt={item.title}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                (e.target as HTMLElement).style.display = "none";
                              }}
                            />
                          </div>
                        )}
                      </div>

                      {/* Read Article & External link footer */}
                      <div className="mt-4 flex items-center justify-between pt-2 border-t border-stone-100 text-xs font-sans">
                        <Link
                          href={`/article/${item.article_id}`}
                          className="font-bold text-stone-900 hover:text-red-800 flex items-center gap-1 uppercase tracking-wider text-[11px]"
                        >
                          Read Article <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                        {item.source_url && (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-stone-400 hover:text-stone-600 flex items-center gap-1 text-[11px]"
                          >
                            Publisher Site <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </article>
                  ))}
                </div>

                {/* Pagination Controls */}
                {searchResponse.total_pages > 1 && (
                  <div className="flex items-center justify-between border-t-2 border-stone-900 pt-4 mt-8 font-sans text-xs">
                    <button
                      type="button"
                      disabled={page <= 1}
                      onClick={() => executeSearch(page - 1)}
                      className="px-4 py-2 border border-stone-300 font-bold uppercase tracking-wider hover:bg-stone-100 disabled:opacity-40 transition-colors flex items-center gap-1"
                    >
                      <ChevronLeft className="w-4 h-4" /> Previous
                    </button>
                    <span className="text-stone-600">
                      Page <strong>{searchResponse.page}</strong> of{" "}
                      <strong>{searchResponse.total_pages}</strong>
                    </span>
                    <button
                      type="button"
                      disabled={page >= searchResponse.total_pages}
                      onClick={() => executeSearch(page + 1)}
                      className="px-4 py-2 border border-stone-300 font-bold uppercase tracking-wider hover:bg-stone-100 disabled:opacity-40 transition-colors flex items-center gap-1"
                    >
                      Next <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </section>
            )}
          </div>
        )}
      </main>

      <Footer />

      {/* Preferences Modals */}
      {onboardingOpen && token && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 font-sans">
          <div className="bg-white max-w-3xl w-full p-6 max-h-[90vh] overflow-y-auto rounded shadow-2xl relative">
            <button
              type="button"
              onClick={() => setOnboardingOpen(false)}
              className="absolute top-4 right-4 text-stone-400 hover:text-stone-700"
            >
              <X className="w-5 h-5" />
            </button>
            <Onboarding
              token={token}
              onComplete={() => setOnboardingOpen(false)}
            />
          </div>
        </div>
      )}
      {token && (
        <MyInterestsModal
          isOpen={interestsModalOpen}
          onClose={() => setInterestsModalOpen(false)}
          token={token}
        />
      )}
    </div>
  );
}
