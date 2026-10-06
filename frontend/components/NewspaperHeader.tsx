"use client";

import React, { useState } from "react";
import Link from "next/link";
import { User } from "@/types";
import {
  Search,
  Bookmark,
  Sliders,
  LogOut,
  User as UserIcon,
  Sparkles,
  Newspaper as NewspaperIcon,
  Menu,
  X,
  Brain,
} from "lucide-react";

interface NewspaperHeaderProps {
  user: User | null;
  onOpenAuth?: () => void;
  onOpenInterests?: () => void;
  onSignOut?: () => void;
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
}

export function NewspaperHeader({
  user,
  onOpenAuth,
  onOpenInterests,
  onSignOut,
  searchQuery = "",
  onSearchChange,
}: NewspaperHeaderProps) {
  const [showMobileMenu, setShowMobileMenu] = useState<boolean>(false);
  const [showSearch, setShowSearch] = useState<boolean>(false);

  const todayStr = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <header className="border-b border-[#DCD3C7] bg-[#FAF8F5] sticky top-0 z-40">
      {/* Top Meta Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-1.5 text-xs text-[#6C645C] flex items-center justify-between border-b border-[#ECE5DA] font-sans">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-[#181615]">{todayStr}</span>
          <span className="hidden sm:inline text-[#B5ABA0]">|</span>
          <span className="hidden sm:inline font-mono text-[11px] uppercase tracking-wider text-[#8C2524]">
            Personalized Daily Edition
          </span>
        </div>

        <div className="flex items-center gap-4">
          {user ? (
            <div className="flex items-center gap-3">
              <span className="hidden sm:inline text-xs text-[#181615]">
                Signed in as <strong className="font-semibold">{user.full_name || user.email}</strong>
              </span>
              {onSignOut && (
                <button
                  onClick={onSignOut}
                  className="text-xs text-[#7A7268] hover:text-[#8C2524] transition-colors flex items-center gap-1"
                >
                  <LogOut className="w-3 h-3" />
                  <span className="hidden sm:inline">Sign Out</span>
                </button>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={onOpenAuth}
                className="font-bold text-[#8C2524] hover:underline"
              >
                Sign In
              </button>
              <span>/</span>
              <button
                onClick={onOpenAuth}
                className="font-semibold text-[#181615] hover:underline"
              >
                Register
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Newspaper Masthead */}
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-5 text-center relative">
        <Link href="/newspaper" className="inline-block group">
          <h1 className="font-editorial-masthead text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-black text-[#110F0E] tracking-tight uppercase group-hover:text-[#8C2524] transition-colors">
            Personalized Newspaper
          </h1>
          <p className="font-editorial-heading italic text-xs sm:text-sm text-[#6C645C] mt-1">
            "Your Daily Intelligence, Filtered by Your True Interests"
          </p>
        </Link>
      </div>

      {/* Navigation & Actions Bar */}
      <div className="border-t-2 border-b-2 border-[#181615] bg-[#FAF8F5]">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 flex items-center justify-between h-12">
          {/* Left Nav links */}
          <nav className="hidden md:flex items-center gap-6 text-xs font-bold uppercase tracking-wider text-[#181615] font-sans">
            <Link
              href="/newspaper"
              className="hover:text-[#8C2524] transition-colors flex items-center gap-1.5 py-2 border-b-2 border-transparent hover:border-[#8C2524]"
            >
              <NewspaperIcon className="w-3.5 h-3.5" />
              <span>Today's Edition</span>
            </Link>

            <Link
              href="/interests"
              className="hover:text-[#8C2524] transition-colors flex items-center gap-1.5 py-2 border-b-2 border-transparent hover:border-[#8C2524]"
            >
              <Brain className="w-3.5 h-3.5 text-[#8C2524]" />
              <span>Interests</span>
            </Link>

            <Link
              href="/history"
              className="hover:text-[#8C2524] transition-colors flex items-center gap-1.5 py-2 border-b-2 border-transparent hover:border-[#8C2524]"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#8C2524]" />
              <span>Reading History</span>
            </Link>

            <Link
              href="/saved"
              className="hover:text-[#8C2524] transition-colors flex items-center gap-1.5 py-2 border-b-2 border-transparent hover:border-[#8C2524]"
            >
              <Bookmark className="w-3.5 h-3.5" />
              <span>Saved Stories</span>
            </Link>

            {user && onOpenInterests && (
              <button
                onClick={onOpenInterests}
                className="hover:text-[#8C2524] transition-colors flex items-center gap-1.5 py-2"
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Quick Preferences</span>
              </button>
            )}
          </nav>

          {/* Mobile menu trigger */}
          <div className="md:hidden flex items-center gap-2">
            <button
              onClick={() => setShowMobileMenu(!showMobileMenu)}
              className="p-2 text-[#181615]"
              aria-label="Toggle menu"
            >
              {showMobileMenu ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <span className="text-xs font-bold uppercase tracking-wider text-[#181615]">
              Menu
            </span>
          </div>

          {/* Right Search Input */}
          <div className="flex items-center gap-3 font-sans">
            {onSearchChange && (
              <div className="relative flex items-center">
                <Search className="w-4 h-4 text-[#7A7268] absolute left-2.5 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search stories..."
                  value={searchQuery}
                  onChange={(e) => onSearchChange(e.target.value)}
                  className="pl-8 pr-3 py-1 text-xs bg-white border border-[#DCD3C7] rounded-sm focus:outline-none focus:border-[#181615] text-[#181615] w-36 sm:w-56"
                />
              </div>
            )}

            {!user && (
              <button
                onClick={onOpenAuth}
                className="hidden sm:inline-flex px-3 py-1.5 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors"
              >
                Sign In
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Nav Dropdown */}
      {showMobileMenu && (
        <div className="md:hidden bg-[#FAF8F5] border-b-2 border-[#181615] px-4 py-3 font-sans text-sm flex flex-col gap-2">
          <Link
            href="/newspaper"
            onClick={() => setShowMobileMenu(false)}
            className="py-2 px-3 hover:bg-[#F3ECE2] font-semibold text-[#181615] flex items-center gap-2"
          >
            <NewspaperIcon className="w-4 h-4" />
            <span>Today's Edition</span>
          </Link>
          <Link
            href="/interests"
            onClick={() => setShowMobileMenu(false)}
            className="py-2 px-3 hover:bg-[#F3ECE2] font-semibold text-[#181615] flex items-center gap-2"
          >
            <Brain className="w-4 h-4 text-[#8C2524]" />
            <span>Interests Engine</span>
          </Link>
          <Link
            href="/history"
            onClick={() => setShowMobileMenu(false)}
            className="py-2 px-3 hover:bg-[#F3ECE2] font-semibold text-[#181615] flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4 text-[#8C2524]" />
            <span>Reading History</span>
          </Link>
          <Link
            href="/saved"
            onClick={() => setShowMobileMenu(false)}
            className="py-2 px-3 hover:bg-[#F3ECE2] font-semibold text-[#181615] flex items-center gap-2"
          >
            <Bookmark className="w-4 h-4" />
            <span>Saved Stories</span>
          </Link>
          {user && onOpenInterests && (
            <button
              onClick={() => {
                setShowMobileMenu(false);
                onOpenInterests();
              }}
              className="py-2 px-3 text-left hover:bg-[#F3ECE2] font-semibold text-[#181615] flex items-center gap-2"
            >
              <Sliders className="w-4 h-4" />
              <span>My Interests</span>
            </button>
          )}
          {!user && (
            <button
              onClick={() => {
                setShowMobileMenu(false);
                onOpenAuth?.();
              }}
              className="py-2 px-3 text-left font-bold text-[#8C2524]"
            >
              Sign In / Register
            </button>
          )}
        </div>
      )}
    </header>
  );
}
