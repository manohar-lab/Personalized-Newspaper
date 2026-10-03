"use client";

import React from "react";
import { ShieldCheck, Cpu, Database, Layout } from "lucide-react";

export function Footer() {
  return (
    <footer className="w-full bg-paper-100 border-t-2 border-ink py-10 px-4 sm:px-8 mt-16 text-paper-800">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-8 mb-8">
        <div className="md:col-span-5 space-y-3">
          <h4 className="font-serif text-2xl font-bold tracking-tight text-ink uppercase">
            Personalized Newspaper
          </h4>
          <p className="font-serif italic text-xs text-gray-700">
            "Your news. Your interests. Your newspaper."
          </p>
          <p className="font-sans text-xs text-gray-600 leading-relaxed max-w-md">
            Production-oriented intelligent news aggregation, classification, and personalized ranking platform built with Next.js, FastAPI, and PostgreSQL.
          </p>
        </div>

        <div className="md:col-span-3 space-y-2 font-sans text-xs">
          <h5 className="font-serif font-bold uppercase tracking-wider text-ink text-sm border-b border-paper-300 pb-1 mb-2">
            Architecture Stack
          </h5>
          <div className="flex items-center space-x-2 text-gray-700">
            <Layout className="h-3.5 w-3.5 text-accent-red" />
            <span>Frontend: Next.js + React + Tailwind</span>
          </div>
          <div className="flex items-center space-x-2 text-gray-700">
            <Cpu className="h-3.5 w-3.5 text-accent-red" />
            <span>Backend: Python + FastAPI</span>
          </div>
          <div className="flex items-center space-x-2 text-gray-700">
            <Database className="h-3.5 w-3.5 text-accent-red" />
            <span>Database: PostgreSQL</span>
          </div>
        </div>

        <div className="md:col-span-4 space-y-2 font-sans text-xs">
          <h5 className="font-serif font-bold uppercase tracking-wider text-ink text-sm border-b border-paper-300 pb-1 mb-2">
            Data & Privacy Policy
          </h5>
          <p className="text-gray-600 leading-relaxed">
            Content is indexed via RSS and permitted web scraping. Licensed full-text articles are rendered natively; restricted publications redirect directly to original publisher sites.
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto border-t border-paper-300 pt-4 flex flex-col sm:flex-row justify-between items-center text-xs text-gray-500 font-sans">
        <div>
          © {new Date().getFullYear()} Personalized Newspaper. Phase 1 Architecture Foundation.
        </div>
        <div className="flex items-center space-x-4 mt-2 sm:mt-0">
          <span>Terms of Service</span>
          <span>•</span>
          <span>Privacy Policy</span>
          <span>•</span>
          <span>Content Syndication</span>
        </div>
      </div>
    </footer>
  );
}
