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
  AlertTriangle,
  Globe,
  FileText,
  Clock,
  ChevronRight,
  RefreshCw,
  Play,
  Activity,
  Layers,
  Sparkles,
  Info,
  Check,
  Zap,
} from "lucide-react";
import { NewspaperHeader } from "@/components/NewspaperHeader";

export default function AdminSourcesPage() {
  const [monitoringData, setMonitoringData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [triggeringIngestion, setTriggeringIngestion] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // URL Extraction Diagnostic State
  const [testUrl, setTestUrl] = useState("");
  const [testingUrl, setTestingUrl] = useState(false);
  const [urlTestResult, setUrlTestResult] = useState<any>(null);

  // Source Test State
  const [testingSourceId, setTestingSourceId] = useState<string | null>(null);
  const [sourceTestResult, setSourceTestResult] = useState<any>(null);

  // Tab State
  const [activeTab, setActiveTab] = useState<"sources" | "feeds" | "jobs" | "diagnostics">("sources");

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadMonitoring = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/admin/sources/monitoring");
      if (res.ok) {
        const data = await res.json();
        setMonitoringData(data);
      }
    } catch (err) {
      console.error("Failed to load monitoring data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMonitoring();
  }, []);

  const handleTriggerIngestion = async () => {
    setTriggeringIngestion(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/admin/ingestion/run", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        showToast(`Ingestion run finished! Processed: ${data.items_processed}, Created: ${data.items_created}`);
        loadMonitoring();
      } else {
        showToast("Ingestion run failed");
      }
    } catch (err) {
      console.error(err);
      showToast("Network error triggering ingestion");
    } finally {
      setTriggeringIngestion(false);
    }
  };

  const handleTestUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testUrl.trim()) return;
    setTestingUrl(true);
    setUrlTestResult(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/extraction/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: testUrl.trim() }),
      });
      const data = await res.json();
      setUrlTestResult(data);
      showToast("Extraction diagnostic complete");
    } catch (err) {
      console.error(err);
      showToast("Diagnostic request failed");
    } finally {
      setTestingUrl(false);
    }
  };

  const handleTestSource = async (sourceId: string) => {
    setTestingSourceId(sourceId);
    setSourceTestResult(null);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/news/sources/${sourceId}/test`, {
        method: "POST",
      });
      const data = await res.json();
      setSourceTestResult(data);
      showToast(`Source test complete: ${data.success ? "Healthy" : "Issues Found"}`);
    } catch (err) {
      console.error(err);
      showToast("Source test request failed");
    } finally {
      setTestingSourceId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "HEALTHY":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-serif font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <ShieldCheck className="w-3 h-3" /> Healthy
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
      case "BLOCKED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-serif font-semibold bg-purple-100 text-purple-800 border border-purple-300">
            <Shield className="w-3 h-3" /> Robots Blocked
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-serif font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#f8f5f0] text-[#1c1917] flex flex-col font-serif">
      <NewspaperHeader />

      {/* Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#1c1917] text-[#f8f5f0] px-5 py-3 rounded-lg shadow-xl text-sm font-sans flex items-center gap-2 border border-[#d6cebf] animate-fade-in">
          <Info className="w-4 h-4 text-[#d97706]" />
          {toastMessage}
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="border-b-2 border-[#1c1917] pb-6 mb-8 flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-[#78716c] mb-1">
              Phase 20 • Real Web Intelligence & Controlled News Ingestion
            </p>
            <h1 className="text-3xl sm:text-4xl font-black font-serif tracking-tight text-[#1c1917]">
              SOURCE & FEED INGESTION REGISTRY
            </h1>
            <p className="mt-1 text-sm text-[#57534e]">
              Conditional request monitoring (ETag/304), SSRF protections, robots.txt compliance, and quality scoring.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadMonitoring}
              className="px-3.5 py-2 bg-white text-[#1c1917] border border-[#d6cebf] rounded-lg text-xs font-sans font-medium hover:bg-[#f0ebe1] flex items-center gap-1.5 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
            <button
              onClick={handleTriggerIngestion}
              disabled={triggeringIngestion}
              className="px-4 py-2 bg-[#1c1917] text-white rounded-lg text-xs font-sans font-medium hover:bg-black flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <Zap className="w-3.5 h-3.5 text-[#d97706]" />
              {triggeringIngestion ? "Ingesting..." : "Run Ingestion Round"}
            </button>
          </div>
        </div>

        {/* Monitoring Metrics Banner */}
        {monitoringData && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <div className="bg-white p-4 rounded-xl border border-[#d6cebf] shadow-sm">
              <p className="text-[11px] font-mono uppercase text-[#78716c]">Active Sources</p>
              <p className="text-2xl font-bold font-serif text-[#1c1917] mt-1">
                {monitoringData.summary.total_sources}
              </p>
              <p className="text-xs text-emerald-700 mt-1 font-sans">
                {monitoringData.summary.healthy_sources} Healthy • {monitoringData.summary.degraded_sources} Degraded
              </p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-[#d6cebf] shadow-sm">
              <p className="text-[11px] font-mono uppercase text-[#78716c]">Registered Feeds</p>
              <p className="text-2xl font-bold font-serif text-[#1c1917] mt-1">
                {monitoringData.summary.total_feeds}
              </p>
              <p className="text-xs text-[#57534e] mt-1 font-sans">RSS / Atom / RDF</p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-[#d6cebf] shadow-sm">
              <p className="text-[11px] font-mono uppercase text-[#78716c]">Extracted Articles</p>
              <p className="text-2xl font-bold font-serif text-[#1c1917] mt-1">
                {monitoringData.extraction_distribution?.SUCCESS || 0}
              </p>
              <p className="text-xs text-amber-700 mt-1 font-sans">
                {monitoringData.extraction_distribution?.PAYWALL || 0} Paywalled • {monitoringData.extraction_distribution?.ROBOTS_BLOCKED || 0} Blocked
              </p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-[#d6cebf] shadow-sm">
              <p className="text-[11px] font-mono uppercase text-[#78716c]">Recent Jobs</p>
              <p className="text-2xl font-bold font-serif text-[#1c1917] mt-1">
                {monitoringData.recent_jobs?.length || 0}
              </p>
              <p className="text-xs text-[#78716c] mt-1 font-sans">Fault Isolated Worker Pool</p>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex border-b border-[#d6cebf] mb-6 gap-6 font-sans text-sm">
          <button
            onClick={() => setActiveTab("sources")}
            className={`pb-3 font-semibold border-b-2 transition-colors ${
              activeTab === "sources"
                ? "border-[#1c1917] text-[#1c1917]"
                : "border-transparent text-[#78716c] hover:text-[#1c1917]"
            }`}
          >
            Sources Registry ({monitoringData?.sources?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab("feeds")}
            className={`pb-3 font-semibold border-b-2 transition-colors ${
              activeTab === "feeds"
                ? "border-[#1c1917] text-[#1c1917]"
                : "border-transparent text-[#78716c] hover:text-[#1c1917]"
            }`}
          >
            Feeds Registry ({monitoringData?.feeds?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab("diagnostics")}
            className={`pb-3 font-semibold border-b-2 transition-colors ${
              activeTab === "diagnostics"
                ? "border-[#1c1917] text-[#1c1917]"
                : "border-transparent text-[#78716c] hover:text-[#1c1917]"
            }`}
          >
            Extraction Diagnostics & URL Tester
          </button>
          <button
            onClick={() => setActiveTab("jobs")}
            className={`pb-3 font-semibold border-b-2 transition-colors ${
              activeTab === "jobs"
                ? "border-[#1c1917] text-[#1c1917]"
                : "border-transparent text-[#78716c] hover:text-[#1c1917]"
            }`}
          >
            Ingestion Job Logs
          </button>
        </div>

        {/* TAB 1: Sources */}
        {activeTab === "sources" && (
          <div className="bg-white rounded-xl border border-[#d6cebf] shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-sans">
                <thead className="bg-[#f0ebe1] text-[#78716c] uppercase font-mono text-[11px] border-b border-[#d6cebf]">
                  <tr>
                    <th className="p-3.5">Source Name</th>
                    <th className="p-3.5">Domain</th>
                    <th className="p-3.5">Health</th>
                    <th className="p-3.5">Quality</th>
                    <th className="p-3.5">Robots</th>
                    <th className="p-3.5">Success / Fail</th>
                    <th className="p-3.5">Last Success</th>
                    <th className="p-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#f0ebe1]">
                  {monitoringData?.sources?.map((s: any) => (
                    <tr key={s.id} className="hover:bg-[#f8f5f0]">
                      <td className="p-3.5 font-bold font-serif text-sm text-[#1c1917]">{s.name}</td>
                      <td className="p-3.5 font-mono text-slate-600">{s.domain || "—"}</td>
                      <td className="p-3.5">{getStatusBadge(s.health_status)}</td>
                      <td className="p-3.5 font-mono font-bold text-[#1c1917]">{Math.round(s.quality_score * 100)}%</td>
                      <td className="p-3.5 font-mono text-[11px]">{s.robots_status}</td>
                      <td className="p-3.5 font-mono text-slate-600">
                        <span className="text-emerald-700">{s.success_count}</span> /{" "}
                        <span className="text-rose-700">{s.failure_count}</span>
                      </td>
                      <td className="p-3.5 text-slate-500">
                        {s.last_success_at ? new Date(s.last_success_at).toLocaleDateString() : "Never"}
                      </td>
                      <td className="p-3.5 text-right">
                        <button
                          onClick={() => handleTestSource(s.id)}
                          disabled={testingSourceId === s.id}
                          className="px-2.5 py-1 bg-[#f0ebe1] hover:bg-[#e7e1d5] text-[#1c1917] rounded text-xs font-sans font-medium transition-colors"
                        >
                          {testingSourceId === s.id ? "Testing..." : "Test Feeds"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Source Test Modal Result */}
            {sourceTestResult && (
              <div className="p-5 bg-[#f8f5f0] border-t border-[#d6cebf]">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="font-bold text-sm text-[#1c1917]">
                    Feed Diagnostic Results for {sourceTestResult.source_name}
                  </h3>
                  <button
                    onClick={() => setSourceTestResult(null)}
                    className="text-xs text-[#78716c] hover:underline"
                  >
                    Close
                  </button>
                </div>
                <div className="space-y-2">
                  {sourceTestResult.tested_feeds.map((tf: any, idx: number) => (
                    <div key={idx} className="p-3 bg-white rounded border border-[#d6cebf] text-xs font-mono">
                      <div className="flex justify-between items-center">
                        <span className="font-bold">{tf.feed_name}</span>
                        <span className={tf.status === "SUCCESS" ? "text-emerald-700 font-bold" : "text-amber-700"}>
                          {tf.status}
                        </span>
                      </div>
                      <p className="text-slate-600 mt-1">
                        Processed: {tf.items_processed} • Created: {tf.items_created} • 304 Skipped:{" "}
                        {tf.items_skipped_304 ? "Yes" : "No"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Feeds */}
        {activeTab === "feeds" && (
          <div className="bg-white rounded-xl border border-[#d6cebf] shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-sans">
                <thead className="bg-[#f0ebe1] text-[#78716c] uppercase font-mono text-[11px] border-b border-[#d6cebf]">
                  <tr>
                    <th className="p-3.5">Feed Name</th>
                    <th className="p-3.5">Feed URL</th>
                    <th className="p-3.5">HTTP Status</th>
                    <th className="p-3.5">ETag / Last-Modified</th>
                    <th className="p-3.5">Health</th>
                    <th className="p-3.5">Last Fetched</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#f0ebe1]">
                  {monitoringData?.feeds?.map((f: any) => (
                    <tr key={f.id} className="hover:bg-[#f8f5f0]">
                      <td className="p-3.5 font-bold font-serif text-[#1c1917]">{f.name}</td>
                      <td className="p-3.5 font-mono text-slate-600 max-w-xs truncate" title={f.feed_url}>
                        {f.feed_url}
                      </td>
                      <td className="p-3.5 font-mono font-bold">
                        <span className={f.http_status === 200 || f.http_status === 304 ? "text-emerald-700" : "text-amber-700"}>
                          {f.http_status || "—"}
                        </span>
                      </td>
                      <td className="p-3.5 font-mono text-[11px] text-slate-500">
                        {f.etag ? `ETag: ${f.etag.slice(0, 16)}...` : f.last_modified || "None"}
                      </td>
                      <td className="p-3.5">{getStatusBadge(f.health_status)}</td>
                      <td className="p-3.5 text-slate-500">
                        {f.last_fetched_at ? new Date(f.last_fetched_at).toLocaleTimeString() : "Never"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: Diagnostics & URL Tester */}
        {activeTab === "diagnostics" && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl border border-[#d6cebf] shadow-sm">
              <h2 className="text-xl font-bold font-serif text-[#1c1917] mb-2">Live Article URL Extraction Diagnostic</h2>
              <p className="text-xs text-[#57534e] mb-4">
                Test how the ingestion system fetches, validates robots.txt, strips tracking params, parses JSON-LD / OpenGraph, and scores article quality for any live web URL.
              </p>

              <form onSubmit={handleTestUrl} className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://example.com/news/article-headline"
                  value={testUrl}
                  onChange={(e) => setTestUrl(e.target.value)}
                  className="flex-1 p-2.5 rounded-lg border border-[#d6cebf] text-sm text-[#1c1917] focus:outline-none focus:ring-2 focus:ring-[#1c1917] font-sans"
                />
                <button
                  type="submit"
                  disabled={testingUrl}
                  className="px-5 py-2.5 bg-[#1c1917] text-white rounded-lg text-xs font-sans font-medium hover:bg-black transition-colors disabled:opacity-50 flex items-center gap-1.5"
                >
                  {testingUrl ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  Test Extraction
                </button>
              </form>
            </div>

            {/* Diagnostic Result Card */}
            {urlTestResult && (
              <div className="bg-white p-6 rounded-xl border border-[#d6cebf] shadow-sm space-y-4 animate-fade-in">
                <div className="flex justify-between items-start border-b border-[#f0ebe1] pb-4">
                  <div>
                    <span className="text-xs font-mono uppercase text-[#78716c]">Extraction Status</span>
                    <h3 className="text-xl font-bold font-serif text-[#1c1917] mt-0.5">
                      {urlTestResult.title || "Untitled Article"}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(urlTestResult.extraction_status)}
                    <span className="text-xs font-mono font-bold bg-[#f0ebe1] px-2.5 py-1 rounded">
                      Quality: {Math.round(urlTestResult.quality_score * 100)}%
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-[#f8f5f0] rounded-lg border border-[#d6cebf] text-xs font-sans">
                  <div>
                    <p className="text-[10px] font-mono text-[#78716c] uppercase">HTTP Status</p>
                    <p className="font-bold text-[#1c1917]">{urlTestResult.http_status}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-mono text-[#78716c] uppercase">Robots Access</p>
                    <p className="font-bold text-[#1c1917]">{urlTestResult.robots_status}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-mono text-[#78716c] uppercase">Content Length</p>
                    <p className="font-bold text-[#1c1917]">{urlTestResult.content_length} chars</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-mono text-[#78716c] uppercase">Reading Time</p>
                    <p className="font-bold text-[#1c1917]">{urlTestResult.reading_time_minutes} min</p>
                  </div>
                </div>

                {/* Canonical URL & Details */}
                <div className="text-xs font-sans space-y-1.5 pt-2">
                  <p className="text-slate-600">
                    <span className="font-semibold text-[#1c1917]">Canonical URL:</span>{" "}
                    <span className="font-mono">{urlTestResult.canonical_url}</span>
                  </p>
                  {urlTestResult.author && (
                    <p className="text-slate-600">
                      <span className="font-semibold text-[#1c1917]">Author:</span> {urlTestResult.author}
                    </p>
                  )}
                  {urlTestResult.quality_flags?.length > 0 && (
                    <div className="flex items-center gap-1 mt-2">
                      <span className="font-semibold text-[#1c1917]">Quality Flags:</span>
                      {urlTestResult.quality_flags.map((flag: string, i: number) => (
                        <span key={i} className="px-2 py-0.5 bg-amber-50 text-amber-800 rounded font-mono text-[10px] border border-amber-200">
                          {flag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Article Snippet */}
                {urlTestResult.snippet && (
                  <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs font-serif leading-relaxed text-slate-800">
                    <p className="font-mono text-[10px] uppercase text-slate-500 mb-1">Extracted Clean Content Preview</p>
                    {urlTestResult.snippet}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: Ingestion Job Logs */}
        {activeTab === "jobs" && (
          <div className="bg-white rounded-xl border border-[#d6cebf] shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-sans">
                <thead className="bg-[#f0ebe1] text-[#78716c] uppercase font-mono text-[11px] border-b border-[#d6cebf]">
                  <tr>
                    <th className="p-3.5">Job ID</th>
                    <th className="p-3.5">Type</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5">Processed</th>
                    <th className="p-3.5">Created</th>
                    <th className="p-3.5">Updated</th>
                    <th className="p-3.5">Failed</th>
                    <th className="p-3.5">Started At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#f0ebe1]">
                  {monitoringData?.recent_jobs?.map((j: any) => (
                    <tr key={j.id} className="hover:bg-[#f8f5f0]">
                      <td className="p-3.5 font-mono text-slate-500">{j.id.slice(0, 8)}...</td>
                      <td className="p-3.5 font-bold font-mono">{j.job_type}</td>
                      <td className="p-3.5">
                        <span className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold ${
                          j.status === "COMPLETED" ? "bg-emerald-100 text-emerald-800" :
                          j.status === "RUNNING" ? "bg-blue-100 text-blue-800" : "bg-rose-100 text-rose-800"
                        }`}>
                          {j.status}
                        </span>
                      </td>
                      <td className="p-3.5 font-mono">{j.items_processed}</td>
                      <td className="p-3.5 font-mono text-emerald-700 font-bold">{j.items_created}</td>
                      <td className="p-3.5 font-mono text-blue-700">{j.items_updated}</td>
                      <td className="p-3.5 font-mono text-rose-700">{j.items_failed}</td>
                      <td className="p-3.5 text-slate-500">
                        {new Date(j.started_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
