"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { Footer } from "@/components/Footer";
import { fetchAdminJobs, retryAdminJob, fetchAdminSchedulerStatus } from "@/lib/api";
import {
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Play,
  Layers,
  Activity,
  Cpu,
  RotateCw,
  ChevronRight,
  ShieldCheck,
  Zap,
} from "lucide-react";

export default function AdminJobsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [schedulerInfo, setSchedulerInfo] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [page, setPage] = useState<number>(1);

  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token") || localStorage.getItem("token");
    setToken(savedToken);
  }, []);

  const loadData = async (t: string) => {
    setLoading(true);
    try {
      const [schedRes, jobsRes] = await Promise.allSettled([
        fetchAdminSchedulerStatus(t),
        fetchAdminJobs({ status: statusFilter || undefined, page, limit: 20 }, t),
      ]);

      if (schedRes.status === "fulfilled") {
        setSchedulerInfo(schedRes.value);
      }
      if (jobsRes.status === "fulfilled") {
        setJobs(jobsRes.value.items || []);
        setTotal(jobsRes.value.total || 0);
      }
    } catch (err) {
      console.warn("Error loading admin jobs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadData(token);
    }
  }, [token, statusFilter, page]);

  const handleRetry = async (jobId: string) => {
    if (!token) return;
    setRetryingId(jobId);
    try {
      await retryAdminJob(jobId, token);
      await loadData(token);
    } catch (err) {
      alert("Failed to retry job");
    } finally {
      setRetryingId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status?.toUpperCase()) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
            <CheckCircle2 className="w-3 h-3" /> COMPLETED
          </span>
        );
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 animate-pulse">
            <RotateCw className="w-3 h-3 animate-spin" /> RUNNING
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300">
            <AlertTriangle className="w-3 h-3" /> FAILED
          </span>
        );
      case "QUEUED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300">
            <Clock className="w-3 h-3" /> QUEUED
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400">
            {status}
          </span>
        );
    }
  };

  const getPriorityBadge = (p: string) => {
    switch (p?.toUpperCase()) {
      case "CRITICAL":
        return <span className="text-[10px] font-bold uppercase text-rose-600">CRITICAL</span>;
      case "HIGH":
        return <span className="text-[10px] font-bold uppercase text-amber-600">HIGH</span>;
      default:
        return <span className="text-[10px] font-bold uppercase text-stone-500">{p || "NORMAL"}</span>;
    }
  };

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
          <span className="text-stone-400">Background Job Queue</span>
        </div>

        {/* Header Title */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-stone-200 dark:border-stone-800 pb-6 mb-8">
          <div>
            <h1 className="font-serif text-3xl font-bold">Autonomous Job Queue</h1>
            <p className="text-xs text-stone-600 dark:text-stone-400 mt-1">
              Real-time monitoring and controls for autonomous newsroom background tasks.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/admin/editions"
              className="px-4 py-2 border border-stone-300 dark:border-stone-700 rounded text-xs font-semibold hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
            >
              Monitor Editions →
            </Link>
            <button
              onClick={() => token && loadData(token)}
              disabled={loading}
              className="px-4 py-2 bg-[#181615] text-[#FBF9F5] dark:bg-[#E8E6E3] dark:text-[#181615] rounded text-xs font-semibold flex items-center gap-2 hover:opacity-90 transition-opacity"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>
        </div>

        {/* Scheduler Stats Cards */}
        {schedulerInfo && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <div className="p-4 bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded">
              <div className="text-xs text-stone-500 font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-emerald-600" /> Scheduler State
              </div>
              <div className="text-xl font-bold font-mono">
                {schedulerInfo.scheduler?.running ? "RUNNING" : "STOPPED"}
              </div>
              <div className="text-[11px] text-stone-400 mt-1">
                {schedulerInfo.scheduler?.jobs_count || 0} autonomous schedules
              </div>
            </div>

            <div className="p-4 bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded">
              <div className="text-xs text-stone-500 font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-600" /> Queued Jobs
              </div>
              <div className="text-xl font-bold font-mono">
                {schedulerInfo.queue_stats?.queued || 0}
              </div>
              <div className="text-[11px] text-stone-400 mt-1">Awaiting execution</div>
            </div>

            <div className="p-4 bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded">
              <div className="text-xs text-stone-500 font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-blue-600" /> In Flight
              </div>
              <div className="text-xl font-bold font-mono">
                {schedulerInfo.queue_stats?.running || 0}
              </div>
              <div className="text-[11px] text-stone-400 mt-1">Actively executing</div>
            </div>

            <div className="p-4 bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded">
              <div className="text-xs text-stone-500 font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Completed
              </div>
              <div className="text-xl font-bold font-mono">
                {schedulerInfo.queue_stats?.completed || 0}
              </div>
              <div className="text-[11px] text-stone-400 mt-1">
                {schedulerInfo.queue_stats?.failed || 0} failed
              </div>
            </div>
          </div>
        )}

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <span className="text-xs font-bold uppercase tracking-wider text-stone-500 mr-2">Filter:</span>
          {["", "QUEUED", "RUNNING", "COMPLETED", "FAILED"].map((s) => (
            <button
              key={s}
              onClick={() => {
                setStatusFilter(s);
                setPage(1);
              }}
              className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
                statusFilter === s
                  ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
                  : "bg-stone-200/70 dark:bg-stone-800 text-stone-700 dark:text-stone-300 hover:bg-stone-300"
              }`}
            >
              {s || "ALL"}
            </button>
          ))}
        </div>

        {/* Jobs Table */}
        <div className="bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded-lg overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-sans">
              <thead className="bg-stone-100 dark:bg-stone-800/60 text-stone-600 dark:text-stone-300 uppercase tracking-wider text-[10px] font-bold border-b border-stone-200 dark:border-stone-800">
                <tr>
                  <th className="py-3 px-4">Job Type</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Attempts</th>
                  <th className="py-3 px-4">Scheduled</th>
                  <th className="py-3 px-4">Completed</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200 dark:divide-stone-800">
                {loading && jobs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-stone-500">
                      Loading job queue...
                    </td>
                  </tr>
                ) : jobs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-stone-500">
                      No jobs found in queue.
                    </td>
                  </tr>
                ) : (
                  jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-stone-50 dark:hover:bg-stone-800/40 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-stone-800 dark:text-stone-200">
                        {job.job_type}
                      </td>
                      <td className="py-3 px-4">{getPriorityBadge(job.priority)}</td>
                      <td className="py-3 px-4">{getStatusBadge(job.status)}</td>
                      <td className="py-3 px-4 font-mono">
                        {job.attempts}/{job.max_attempts}
                      </td>
                      <td className="py-3 px-4 text-stone-500">
                        {job.scheduled_at ? new Date(job.scheduled_at).toLocaleTimeString() : "-"}
                      </td>
                      <td className="py-3 px-4 text-stone-500">
                        {job.completed_at ? new Date(job.completed_at).toLocaleTimeString() : "-"}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {(job.status === "FAILED" || job.status === "CANCELLED") && (
                          <button
                            onClick={() => handleRetry(job.id)}
                            disabled={retryingId === job.id}
                            className="px-2.5 py-1 text-[11px] font-bold bg-stone-800 text-white dark:bg-stone-200 dark:text-stone-900 rounded hover:opacity-80 transition-opacity"
                          >
                            {retryingId === job.id ? "Retrying..." : "Retry"}
                          </button>
                        )}
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
