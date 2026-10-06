"use client";

import React from "react";
import { BackendStatusBadge } from "./BackendStatusBadge";
import { Newspaper, Sliders, User as UserIcon, LogOut, Sparkles } from "lucide-react";
import { User } from "@/types";

interface HeaderProps {
  user: User | null;
  onOpenAuth: () => void;
  onOpenOnboarding: () => void;
  onOpenInterests: () => void;
  onSignOut: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  onOpenAuth,
  onOpenOnboarding,
  onOpenInterests,
  onSignOut,
}) => {
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
      <div className="text-center py-4 border-b-2 border-[#121212]">
        <h1 className="font-serif text-4xl sm:text-6xl md:text-7xl font-bold tracking-tight text-[#121212] uppercase">
          Personalized Newspaper
        </h1>
        <p className="font-serif italic text-sm sm:text-base text-gray-700 mt-1">
          &ldquo;Your news. Your interests. Your newspaper.&rdquo;
        </p>
      </div>

      {/* Navigation Bar */}
      <nav className="flex justify-between items-center py-2.5 border-b border-[#D3CBB9] text-xs font-semibold uppercase tracking-wider text-[#121212]">
        <div className="flex items-center space-x-4 sm:space-x-6 overflow-x-auto py-1">
          <a
            href="/"
            className="hover:text-red-700 transition-colors flex items-center gap-1.5 font-bold pb-0.5 shrink-0"
          >
            <Newspaper className="h-3.5 w-3.5" /> Front Page
          </a>
          <a
            href="/search"
            className="hover:text-red-700 transition-colors flex items-center gap-1.5 font-bold uppercase shrink-0 text-gray-800"
          >
            🔎 Search Engine
          </a>
          <a
            href="/history"
            className="hover:text-red-700 transition-colors flex items-center gap-1.5 font-bold uppercase shrink-0 text-gray-800"
          >
            📖 Reading History
          </a>
          <button
            type="button"
            onClick={user ? onOpenOnboarding : onOpenAuth}
            className="hover:text-red-700 transition-colors flex items-center gap-1.5 text-gray-700 font-bold uppercase shrink-0"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-600" /> Onboarding Setup
          </button>

          {user && (
            <button
              type="button"
              onClick={onOpenInterests}
              className="hover:text-red-700 transition-colors flex items-center gap-1.5 text-gray-700 uppercase shrink-0"
            >
              <Sliders className="h-3.5 w-3.5" /> Stored Preferences
            </button>
          )}
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          {user ? (
            <div className="flex items-center space-x-3 font-sans">
              <span className="text-xs text-gray-700 hidden sm:inline font-bold">
                {user.profile?.display_name || user.full_name || user.email}
              </span>
              <button
                type="button"
                onClick={onOpenInterests}
                className="px-2.5 py-1 bg-emerald-800 text-white rounded text-[11px] font-sans font-semibold uppercase hover:bg-emerald-900 transition-colors"
              >
                Preferences
              </button>
              <button
                type="button"
                onClick={onSignOut}
                className="p-1 text-gray-600 hover:text-red-700 transition-colors"
                title="Sign Out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onOpenAuth}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-[#121212] text-white rounded hover:bg-gray-800 transition-colors text-xs font-sans font-medium uppercase tracking-wider"
            >
              <UserIcon className="h-3.5 w-3.5" /> Sign In / Register
            </button>
          )}
        </div>
      </nav>
    </header>
  );
};
