"use client";

import React from "react";
import { BackendStatusBadge } from "./BackendStatusBadge";
import { Newspaper, Bookmark, Compass, Sliders, User } from "lucide-react";

export function Header() {
  const currentDate = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <header className="w-full bg-paper-50 pt-4 pb-2 px-4 sm:px-8 max-w-7xl mx-auto">
      {/* Top Meta Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-center text-xs text-paper-800 border-b border-paper-300 pb-2 mb-3 gap-2">
        <div className="font-serif italic text-gray-600">
          {currentDate} • Daily Edition
        </div>
        <div className="flex items-center space-x-4">
          <BackendStatusBadge />
        </div>
      </div>

      {/* Main Newspaper Masthead */}
      <div className="text-center py-4 border-b-2 border-ink">
        <h1 className="font-serif text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight text-ink uppercase">
          Personalized Newspaper
        </h1>
        <p className="font-serif italic text-sm sm:text-base text-gray-700 mt-1">
          "Your news. Your interests. Your newspaper."
        </p>
      </div>

      {/* Navigation Bar */}
      <nav className="flex justify-between items-center py-2.5 border-b border-paper-300 text-xs font-semibold uppercase tracking-wider text-ink">
        <div className="flex items-center space-x-6 overflow-x-auto py-1">
          <a href="#front-page" className="hover:text-accent-red transition-colors flex items-center gap-1.5 font-bold border-b-2 border-accent-red pb-0.5">
            <Newspaper className="h-3.5 w-3.5" /> Front Page
          </a>
          <a href="#interests" className="hover:text-accent-red transition-colors flex items-center gap-1.5 text-gray-600">
            <Sliders className="h-3.5 w-3.5" /> My Interests
          </a>
          <a href="#saved" className="hover:text-accent-red transition-colors flex items-center gap-1.5 text-gray-600">
            <Bookmark className="h-3.5 w-3.5" /> Saved Edition
          </a>
          <a href="#discover" className="hover:text-accent-red transition-colors flex items-center gap-1.5 text-gray-600">
            <Compass className="h-3.5 w-3.5" /> Explore Sources
          </a>
        </div>
        <div className="flex items-center space-x-3">
          <button className="flex items-center space-x-1.5 px-3 py-1 bg-ink text-paper-50 rounded hover:bg-gray-800 transition-colors text-xs font-sans capitalize font-medium">
            <User className="h-3.5 w-3.5" /> Sign In
          </button>
        </div>
      </nav>
    </header>
  );
}
