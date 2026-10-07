"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { Footer } from "@/components/Footer";
import { fetchAdminEditions } from "@/lib/api";
import {
  RefreshCw,
  Layers,
  ChevronRight,
  BookOpen,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ExternalLink,
} from "lucide-react";

export default function AdminEditionsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [editions, setEditions] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [page, setPage] = useState<number>(1);

  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token") || localStorage.getItem("token");
    setToken(savedToken);
  }, []);

  const loadData = async (t: string) => {
    setLoading(true);
    try {
      const res = await fetchAdminEditions(page, 20, t);
      setEditions(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.warn("Error loading admin editions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadData(token);
    }
  }, [token, page]);

  return (
    <div className="min-h-screen bg-[#FBF9F5] dark:bg-[#121110] text-[#181615] dark:text-[#E8E6E3]">
      <NewspaperHeader />

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-stone-500 mb-6">
          <Link href="/newspaper" className="hover:underline">Home</Link>
          <ChevronRight className="w-3 h-3" />
          <span className="font-semibold text-stone-800 dark:text-stone-200">Admin Operations</span>
          <ChevronRight className="w-3 h-3" />
          <span className="text-stone-400">Editions Monitor</span>
        </div>

        {/* Title Row */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-stone-200 dark:border-stone-800 pb-6 mb-8">
          <div>
            <h1 className="font-serif text-3xl font-bold">Newspaper Editions Monitor</h1>
            <p className="text-xs text-stone-600 dark:text-stone-400 mt-1">
              Global oversight of immutable newspaper editions generated across all active readers.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/admin/jobs"
              className="px-4 py-2 border border-stone-300 dark:border-stone-700 rounded text-xs font-semibold hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
            >
              ← Job Queue
            </Link>
            <button
              onClick={() => token && loadData(token)}
              disabled={loading}
              className="px-4 py-2 bg-[#181615] text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] rounded text-xs font-semibold flex items-center gap-2 hover:opacity-90"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded-lg overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-sans">
              <thead className="bg-stone-100 dark:bg-stone-800/60 text-stone-600 dark:text-stone-300 uppercase tracking-wider text-[10px] font-bold border-b border-stone-200 dark:border-stone-800">
                <tr>
                  <th className="py-3 px-4">Edition Date</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Version</th>
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Generated Time</th>
                  <th className="py-3 px-4 text-right">View</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200 dark:divide-stone-800">
                {loading && editions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-stone-500">
                      Loading editions...
                    </td>
                  </tr>
                ) : editions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-stone-500">
                      No newspaper editions generated yet.
                    </td>
                  </tr>
                ) : (
                  editions.map((ed) => (
                    <tr key={ed.id} className="hover:bg-stone-50 dark:hover:bg-stone-800/40 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-stone-800 dark:text-stone-200 flex items-center gap-2">
                        <Calendar className="w-3.5 h-3.5 text-stone-500" />
                        {ed.edition_date}
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-300">
                          {ed.edition_type || "MORNING"}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono">v{ed.version}</td>
                      <td className="py-3 px-4 font-serif font-bold text-stone-800 dark:text-stone-200">
                        {ed.title}
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" /> {ed.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-stone-500">
                        {ed.generated_at ? new Date(ed.generated_at).toLocaleString() : "-"}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          href={`/newspaper`}
                          className="text-stone-600 dark:text-stone-400 hover:underline flex items-center justify-end gap-1"
                        >
                          Open <ExternalLink className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
