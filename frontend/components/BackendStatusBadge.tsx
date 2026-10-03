"use client";

import React, { useEffect, useState } from "react";
import { fetchBackendHealth, fetchDatabaseHealth } from "@/lib/api";
import { HealthResponse, DatabaseHealthResponse } from "@/types";
import { RefreshCw, Server, Database, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

export function BackendStatusBadge() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [dbHealth, setDbHealth] = useState<DatabaseHealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState<boolean>(false);

  const checkConnection = async () => {
    setLoading(true);
    setError(null);
    try {
      const [backendData, dbData] = await Promise.all([
        fetchBackendHealth(),
        fetchDatabaseHealth().catch((err) => ({
          status: "disconnected",
          database: "postgresql",
          detail: err.message || "Failed to reach database endpoint",
        })),
      ]);
      setHealth(backendData);
      setDbHealth(dbData);
    } catch (err: any) {
      setError(err.message || "Unable to connect to FastAPI backend");
      setHealth(null);
      setDbHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkConnection();
    // Refresh health status every 30 seconds
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  const isConnected = health?.status === "ok";

  return (
    <div className="relative inline-block text-left">
      <div
        onClick={() => setShowDetails(!showDetails)}
        className={`cursor-pointer flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all shadow-sm border ${
          loading
            ? "bg-amber-50 text-amber-800 border-amber-200"
            : isConnected
            ? "bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100"
            : "bg-rose-50 text-rose-900 border-rose-300 hover:bg-rose-100"
        }`}
        title="Click to view full architecture connection status"
      >
        <span className="relative flex h-2 w-2">
          {loading ? (
            <span className="animate-spin h-2 w-2 rounded-full border-2 border-amber-600 border-t-transparent"></span>
          ) : isConnected ? (
            <>
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
            </>
          ) : (
            <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-600"></span>
          )}
        </span>

        <span className="font-sans font-semibold tracking-wide">
          Backend Status: {loading ? "Connecting..." : isConnected ? "Connected" : "Disconnected"}
        </span>

        <button
          onClick={(e) => {
            e.stopPropagation();
            checkConnection();
          }}
          className="ml-1 text-gray-500 hover:text-gray-900 transition-colors"
          title="Refresh connection check"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {showDetails && (
        <div className="absolute right-0 mt-2 w-80 rounded-md bg-white shadow-xl border border-gray-200 p-4 z-50 text-xs text-gray-800 font-sans animate-in fade-in slide-in-from-top-2">
          <div className="flex justify-between items-center pb-2 mb-2 border-b border-gray-100">
            <span className="font-bold uppercase tracking-wider text-gray-700">System Connection Status</span>
            <button
              onClick={() => setShowDetails(false)}
              className="text-gray-400 hover:text-gray-600 font-bold"
            >
              ✕
            </button>
          </div>

          <div className="space-y-3">
            {/* FastAPI Service Status */}
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-2">
                <Server className="h-4 w-4 text-gray-600" />
                <div>
                  <div className="font-semibold">FastAPI Engine</div>
                  <div className="text-gray-500 text-[10px]">{process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}</div>
                </div>
              </div>
              <span className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] ${
                isConnected ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
              }`}>
                {isConnected ? "ONLINE" : "OFFLINE"}
              </span>
            </div>

            {/* PostgreSQL Status */}
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-2">
                <Database className="h-4 w-4 text-gray-600" />
                <div>
                  <div className="font-semibold">PostgreSQL Storage</div>
                  <div className="text-gray-500 text-[10px]">
                    {dbHealth?.detail ? dbHealth.detail : "Checking database status..."}
                  </div>
                </div>
              </div>
              <span className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] ${
                dbHealth?.status === "connected"
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-amber-100 text-amber-800"
              }`}>
                {dbHealth?.status ? dbHealth.status.toUpperCase() : "CHECKING"}
              </span>
            </div>

            {error && (
              <div className="p-2 bg-rose-50 border border-rose-200 rounded text-rose-800 text-[11px] leading-snug">
                <span className="font-bold">Error:</span> {error}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
