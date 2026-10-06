"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  ShieldAlert,
  Shield,
  Search,
  ExternalLink,
  CheckCircle2,
  VolumeX,
  Volume2,
  AlertTriangle,
  Flag,
  Globe,
  FileText,
  Clock,
  ChevronRight,
  X,
  Layers,
  Sparkles,
  Info,
} from "lucide-react";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import {
  fetchSources,
  fetchSourceDetail,
  followSource,
  unfollowSource,
  muteSource,
  unmuteSource,
  reportSource,
  fetchCurrentUser,
} from "@/lib/api";
import { SourceItem, SourceDetail, User } from "@/types";

export default function SourcesPage() {
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [followingOnly, setFollowingOnly] = useState(false);

  // Modal states
  const [selectedSource, setSelectedSource] = useState<SourceDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [reportingSource, setReportingSource] = useState<SourceItem | null>(null);
  const [reportReason, setReportReason] = useState<
    "MISLEADING" | "LOW_QUALITY" | "BROKEN_ARTICLE" | "DUPLICATE" | "PAYWALL" | "OTHER"
  >("LOW_QUALITY");
  const [reportDetails, setReportDetails] = useState("");
  const [submittingReport, setSubmittingReport] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    const t = localStorage.getItem("token");
    setToken(t);
    if (t) {
      fetchCurrentUser(t)
        .then(setUser)
        .catch(() => setUser(null));
    }
  }, []);

  const loadSources = async () => {
    setLoading(true);
    try {
      const res = await fetchSources(
        {
          search: search.trim() || undefined,
          status: statusFilter || undefined,
          following_only: followingOnly,
          limit: 50,
        },
        token || undefined
      );
      setSources(res.sources);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to load sources:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSources();
  }, [search, statusFilter, followingOnly, token]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleFollowToggle = async (source: SourceItem) => {
    if (!token) {
      showToast("Please log in to follow news sources");
      return;
    }
    try {
      if (source.is_following) {
        await unfollowSource(source.id, token);
        setSources((prev) =>
          prev.map((s) => (s.id === source.id ? { ...s, is_following: false } : s))
        );
        showToast(`Unfollowed ${source.name}`);
      } else {
        await followSource(source.id, token);
        setSources((prev) =>
          prev.map((s) =>
            s.id === source.id ? { ...s, is_following: true, is_muted: false } : s
          )
        );
        showToast(`Following ${source.name}`);
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to update source preference");
    }
  };

  const handleMuteToggle = async (source: SourceItem) => {
    if (!token) {
      showToast("Please log in to mute news sources");
      return;
    }
    try {
      if (source.is_muted) {
        await unmuteSource(source.id, token);
        setSources((prev) =>
          prev.map((s) => (s.id === source.id ? { ...s, is_muted: false } : s))
        );
        showToast(`Unmuted ${source.name}`);
      } else {
        await muteSource(source.id, token);
        setSources((prev) =>
          prev.map((s) =>
            s.id === source.id ? { ...s, is_muted: true, is_following: false } : s
          )
        );
        showToast(`Muted ${source.name} from future editions`);
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to update mute preference");
    }
  };

  const openSourceDetail = async (sourceId: string) => {
    setLoadingDetail(true);
    try {
      const detail = await fetchSourceDetail(sourceId, token || undefined);
      setSelectedSource(detail);
    } catch (err) {
      console.error(err);
      showToast("Failed to load source details");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportingSource) return;
    setSubmittingReport(true);
    try {
      await reportSource(
        reportingSource.id,
        {
          reason: reportReason,
          details: reportDetails.trim() || undefined,
        },
        token || undefined
      );
      setReportingSource(null);
      setReportDetails("");
      showToast("Thank you. Quality report recorded for editorial review.");
    } catch (err) {
      console.error(err);
      showToast("Failed to submit source report");
    } finally {
      setSubmittingReport(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "HEALTHY":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-serif font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <ShieldCheck className="w-3 h-3" /> Healthy Feed
          </span>
        );
      case "DEGRADED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-serif font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-3 h-3" /> Degraded
          </span>
        );
      case "FAILING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-serif font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <ShieldAlert className="w-3 h-3" /> Failing
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-serif font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            <Shield className="w-3 h-3" /> Inactive
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#f8f5f0] text-[#1c1917] flex flex-col font-serif">
      <NewspaperHeader user={user} />

      {/* Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#1c1917] text-[#f8f5f0] px-5 py-3 rounded-lg shadow-xl text-sm font-sans flex items-center gap-2 border border-[#d6cebf] animate-fade-in">
          <Info className="w-4 h-4 text-[#d97706]" />
          {toastMessage}
        </div>
      )}

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
        {/* Header Section */}
        <div className="border-b-2 border-[#1c1917] pb-6 mb-8 text-center">
          <p className="text-xs font-mono uppercase tracking-widest text-[#78716c] mb-1">
            Section 15 • Source Intelligence & Quality Engine
          </p>
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-black font-serif tracking-tight text-[#1c1917]">
            NEWS SOURCES & PUBLISHER DIRECTORY
          </h1>
          <p className="mt-2 text-sm sm:text-base text-[#57534e] max-w-2xl mx-auto italic">
            Transparent quality monitoring, feed reliability, and personalized publisher preferences.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="bg-[#f0ebe1] p-4 rounded-xl border border-[#d6cebf] shadow-sm mb-8 flex flex-col sm:flex-row gap-4 justify-between items-stretch sm:items-center">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-3 text-[#78716c]" />
            <input
              type="text"
              placeholder="Search publisher name or description..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white rounded-lg border border-[#d6cebf] text-sm text-[#1c1917] focus:outline-none focus:ring-2 focus:ring-[#1c1917]"
            />
          </div>

          {/* Health Status Filter */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-sans font-medium text-[#78716c] whitespace-nowrap">
              Status:
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-white px-3 py-2 rounded-lg border border-[#d6cebf] text-xs font-sans text-[#1c1917] focus:outline-none focus:ring-2 focus:ring-[#1c1917]"
            >
              <option value="">All Statuses</option>
              <option value="HEALTHY">Healthy Only</option>
              <option value="DEGRADED">Degraded</option>
              <option value="FAILING">Failing</option>
              <option value="INACTIVE">Inactive</option>
            </select>
          </div>

          {/* Following Filter */}
          {token && (
            <button
              onClick={() => setFollowingOnly(!followingOnly)}
              className={`px-4 py-2 rounded-lg text-xs font-sans font-medium border transition-colors flex items-center justify-center gap-1.5 ${
                followingOnly
                  ? "bg-[#1c1917] text-white border-[#1c1917]"
                  : "bg-white text-[#1c1917] border-[#d6cebf] hover:bg-[#e7e1d5]"
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Followed ({followingOnly ? "Active" : "All"})
            </button>
          )}
        </div>

        {/* Source Cards Grid */}
        {loading ? (
          <div className="py-20 text-center text-[#78716c] text-sm">
            <div className="animate-spin w-8 h-8 border-2 border-[#1c1917] border-t-transparent rounded-full mx-auto mb-3" />
            Evaluating publisher sources and health metrics...
          </div>
        ) : sources.length === 0 ? (
          <div className="py-16 text-center border-2 border-dashed border-[#d6cebf] rounded-2xl bg-[#f0ebe1] p-8">
            <Globe className="w-12 h-12 text-[#a8a29e] mx-auto mb-3" />
            <h3 className="text-lg font-serif font-bold text-[#1c1917]">No News Sources Found</h3>
            <p className="text-sm text-[#78716c] mt-1 max-w-md mx-auto">
              No publishers match the selected filter criteria. Try clearing search keywords or status filters.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sources.map((source) => (
              <div
                key={source.id}
                className={`bg-white rounded-xl border p-5 shadow-sm transition-all duration-200 flex flex-col justify-between ${
                  source.is_muted
                    ? "border-slate-300 opacity-60 bg-slate-50"
                    : source.is_following
                    ? "border-[#1c1917] ring-1 ring-[#1c1917]"
                    : "border-[#d6cebf] hover:shadow-md hover:border-[#a8a29e]"
                }`}
              >
                <div>
                  {/* Top Bar: Status Badge + Muted Indicator */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    {getStatusBadge(source.health_status)}
                    {source.is_muted && (
                      <span className="text-xs font-mono text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                        MUTED
                      </span>
                    )}
                  </div>

                  {/* Publisher Title */}
                  <h2 className="text-xl font-bold font-serif text-[#1c1917] hover:text-[#b45309] transition-colors leading-snug">
                    {source.name}
                  </h2>

                  {/* Description */}
                  <p className="text-xs text-[#57534e] mt-2 line-clamp-2 leading-relaxed">
                    {source.description || "Active editorial news publisher integrated into the newspaper pipeline."}
                  </p>

                  {/* Stats Bar */}
                  <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-[#f0ebe1] text-xs font-sans text-[#78716c]">
                    <div className="flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-[#a8a29e]" />
                      <span>{source.article_count} articles</span>
                    </div>
                    <div className="flex items-center gap-1.5 justify-end">
                      <Clock className="w-3.5 h-3.5 text-[#a8a29e]" />
                      <span>Freshness: {Math.round(source.freshness_score * 100)}%</span>
                    </div>
                  </div>
                </div>

                {/* Actions Footer */}
                <div className="mt-5 pt-4 border-t border-[#f0ebe1] flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {/* Follow Toggle */}
                    <button
                      onClick={() => handleFollowToggle(source)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-sans font-medium transition-colors ${
                        source.is_following
                          ? "bg-emerald-700 text-white hover:bg-emerald-800"
                          : "bg-[#f0ebe1] text-[#1c1917] hover:bg-[#e7e1d5]"
                      }`}
                      title={source.is_following ? "Following" : "Follow source"}
                    >
                      {source.is_following ? "Following" : "Follow"}
                    </button>

                    {/* Mute Toggle */}
                    <button
                      onClick={() => handleMuteToggle(source)}
                      className={`p-1.5 rounded-lg text-xs font-sans transition-colors ${
                        source.is_muted
                          ? "bg-rose-700 text-white hover:bg-rose-800"
                          : "text-[#78716c] hover:bg-[#f0ebe1] hover:text-[#1c1917]"
                      }`}
                      title={source.is_muted ? "Unmute Source" : "Mute Source"}
                    >
                      {source.is_muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </button>

                    {/* Report Button */}
                    <button
                      onClick={() => setReportingSource(source)}
                      className="p-1.5 rounded-lg text-xs text-[#78716c] hover:bg-[#f0ebe1] hover:text-amber-700 transition-colors"
                      title="Report source quality issue"
                    >
                      <Flag className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Detail Link */}
                  <button
                    onClick={() => openSourceDetail(source.id)}
                    className="text-xs font-sans font-medium text-[#b45309] hover:underline flex items-center gap-1"
                  >
                    Details <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Source Detail Modal */}
        {selectedSource && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in">
            <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 border border-[#d6cebf] shadow-2xl relative">
              <button
                onClick={() => setSelectedSource(null)}
                className="absolute right-4 top-4 p-2 rounded-full hover:bg-slate-100 text-[#78716c]"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex items-center gap-2 mb-2">
                {getStatusBadge(selectedSource.health_status)}
                {selectedSource.website_url && (
                  <a
                    href={selectedSource.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-[#b45309] hover:underline font-sans"
                  >
                    Visit Website <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>

              <h2 className="text-2xl font-bold font-serif text-[#1c1917]">{selectedSource.name}</h2>
              <p className="text-sm text-[#57534e] mt-2 leading-relaxed">{selectedSource.description}</p>

              {/* Source Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 my-6 p-4 bg-[#f8f5f0] rounded-xl border border-[#d6cebf]">
                <div>
                  <p className="text-[10px] font-mono text-[#78716c] uppercase">Total Articles</p>
                  <p className="text-lg font-bold font-serif text-[#1c1917]">{selectedSource.article_count}</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-[#78716c] uppercase">Feed Feeds</p>
                  <p className="text-lg font-bold font-serif text-[#1c1917]">{selectedSource.feed_count}</p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-[#78716c] uppercase">Extraction Rate</p>
                  <p className="text-lg font-bold font-serif text-[#1c1917]">
                    {Math.round(selectedSource.extraction_success_rate * 100)}%
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-[#78716c] uppercase">Freshness</p>
                  <p className="text-lg font-bold font-serif text-[#1c1917]">
                    {Math.round(selectedSource.freshness_score * 100)}%
                  </p>
                </div>
              </div>

              {/* Recent Articles */}
              <h3 className="text-sm font-bold font-mono uppercase tracking-wider text-[#1c1917] mb-3 flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#b45309]" /> Recent Coverage
              </h3>
              {selectedSource.recent_articles.length === 0 ? (
                <p className="text-xs text-[#78716c] italic">No recent articles extracted yet.</p>
              ) : (
                <div className="space-y-2">
                  {selectedSource.recent_articles.map((art) => (
                    <Link
                      key={art.id}
                      href={`/article/${art.id}`}
                      className="block p-3 rounded-lg border border-[#f0ebe1] hover:border-[#d6cebf] hover:bg-[#f8f5f0] transition-colors"
                    >
                      <h4 className="text-sm font-bold font-serif text-[#1c1917] line-clamp-1">{art.title}</h4>
                      <div className="flex items-center gap-3 mt-1 text-[11px] font-sans text-[#78716c]">
                        <span>{art.reading_time_minutes} min read</span>
                        {art.extraction_status === "PAYWALL" && (
                          <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded font-mono text-[10px]">
                            PAYWALL
                          </span>
                        )}
                        {art.published_at && (
                          <span>{new Date(art.published_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Report Source Modal */}
        {reportingSource && (
          <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 border border-[#d6cebf] shadow-2xl relative font-sans">
              <button
                onClick={() => setReportingSource(null)}
                className="absolute right-4 top-4 p-2 rounded-full hover:bg-slate-100 text-[#78716c]"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex items-center gap-2 text-amber-700 mb-2">
                <Flag className="w-5 h-5" />
                <h3 className="font-bold text-base text-[#1c1917]">Report Quality Issue</h3>
              </div>
              <p className="text-xs text-[#57534e] mb-4">
                Reporting <span className="font-semibold text-[#1c1917]">{reportingSource.name}</span>. Reports help improve feed health and automated source evaluation.
              </p>

              <form onSubmit={handleReportSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1c1917] mb-1">Issue Category</label>
                  <select
                    value={reportReason}
                    onChange={(e: any) => setReportReason(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#d6cebf] text-sm text-[#1c1917] focus:outline-none focus:ring-2 focus:ring-[#1c1917]"
                  >
                    <option value="LOW_QUALITY">Low Content Quality</option>
                    <option value="MISLEADING">Misleading / Clickbait Headlines</option>
                    <option value="PAYWALL">Strict Paywall / Inaccessible</option>
                    <option value="BROKEN_ARTICLE">Broken Feed / Formatting Issues</option>
                    <option value="DUPLICATE">Excessive Duplicate Reprints</option>
                    <option value="OTHER">Other Issue</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#1c1917] mb-1">Optional Details</label>
                  <textarea
                    rows={3}
                    placeholder="Describe the issue you encountered..."
                    value={reportDetails}
                    onChange={(e) => setReportDetails(e.target.value)}
                    className="w-full p-2.5 rounded-lg border border-[#d6cebf] text-sm text-[#1c1917] focus:outline-none focus:ring-2 focus:ring-[#1c1917]"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setReportingSource(null)}
                    className="px-4 py-2 rounded-lg text-xs font-medium text-[#78716c] hover:bg-slate-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submittingReport}
                    className="px-5 py-2 rounded-lg text-xs font-medium bg-[#1c1917] text-white hover:bg-black transition-colors disabled:opacity-50"
                  >
                    {submittingReport ? "Submitting..." : "Submit Report"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
