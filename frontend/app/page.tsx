"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { NewspaperHero } from "@/components/NewspaperHero";
import { NewsSection } from "@/components/NewsSection";
import { Footer } from "@/components/Footer";
import { AuthModal } from "@/components/AuthModal";
import { Onboarding } from "@/components/Onboarding";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { fetchCurrentUser, fetchMyInterests } from "@/lib/api";
import { User, UserInterest } from "@/types";
import { Sparkles, CheckCircle2, Sliders, ArrowRight } from "lucide-react";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [userInterests, setUserInterests] = useState<UserInterest[]>([]);
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [showOnboarding, setShowOnboarding] = useState<boolean>(false);
  const [showInterestsModal, setShowInterestsModal] = useState<boolean>(false);

  // Load token on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token");
    if (savedToken) {
      setToken(savedToken);
      loadUser(savedToken);
    }
  }, []);

  const loadUser = async (authToken: string) => {
    try {
      const u = await fetchCurrentUser(authToken);
      setUser(u);
      const interests = await fetchMyInterests(authToken).catch(() => []);
      setUserInterests(interests);

      // If user has 0 interests set, prompt onboarding automatically
      if (interests.length === 0) {
        setShowOnboarding(true);
      }
    } catch {
      // Invalid or expired token
      localStorage.removeItem("pn_auth_token");
      setToken(null);
      setUser(null);
    }
  };

  const handleAuthSuccess = (newToken: string, newUser: User) => {
    localStorage.setItem("pn_auth_token", newToken);
    setToken(newToken);
    setUser(newUser);
    setShowOnboarding(true);
  };

  const handleSignOut = () => {
    localStorage.removeItem("pn_auth_token");
    setToken(null);
    setUser(null);
    setUserInterests([]);
    setShowOnboarding(false);
  };

  const handleOnboardingComplete = async () => {
    setShowOnboarding(false);
    if (token) {
      const updatedInterests = await fetchMyInterests(token).catch(() => []);
      setUserInterests(updatedInterests);
    }
  };

  const posCount = userInterests.filter((i) => i.preference_type === "POSITIVE").length;
  const negCount = userInterests.filter((i) => i.preference_type === "NEGATIVE").length;

  return (
    <main className="min-h-screen flex flex-col justify-between bg-[#FAF9F5] selection:bg-red-700 selection:text-white">
      <div>
        <Header
          user={user}
          onOpenAuth={() => setShowAuthModal(true)}
          onOpenOnboarding={() => {
            if (!token) setShowAuthModal(true);
            else setShowOnboarding(true);
          }}
          onOpenInterests={() => setShowInterestsModal(true)}
          onSignOut={handleSignOut}
        />

        {/* Phase 2 Personalization Foundation Status Banner */}
        {user && (
          <div className="max-w-7xl mx-auto px-4 sm:px-8 my-4">
            <div className="bg-[#F3EFE6] border-2 border-[#121212] p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 font-serif">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-700 shrink-0" />
                <div>
                  <h3 className="font-bold text-sm text-[#121212] uppercase tracking-wide">
                    Personalized Foundation Active (PostgreSQL)
                  </h3>
                  <p className="text-xs text-[#4A453E] font-sans">
                    Authenticated as <span className="font-bold text-[#121212]">{user.email}</span>. Stored preferences:{" "}
                    <span className="font-semibold text-emerald-800">{posCount} Positive</span>,{" "}
                    <span className="font-semibold text-rose-800">{negCount} Filtered Out</span>.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 font-sans">
                <button
                  onClick={() => setShowOnboarding(true)}
                  className="px-3 py-1.5 bg-[#121212] text-white text-xs font-bold uppercase tracking-wider hover:bg-[#2A2A2A] transition-colors flex items-center gap-1"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Update Onboarding</span>
                </button>
                <button
                  onClick={() => setShowInterestsModal(true)}
                  className="px-3 py-1.5 bg-white border border-[#121212] text-[#121212] text-xs font-bold uppercase tracking-wider hover:bg-gray-100 transition-colors flex items-center gap-1"
                >
                  <Sliders className="w-3.5 h-3.5" />
                  <span>Inspect DB</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Interactive Onboarding Flow */}
        {showOnboarding && token ? (
          <Onboarding
            token={token}
            onComplete={handleOnboardingComplete}
          />
        ) : (
          <>
            <NewspaperHero />
            <NewsSection />
          </>
        )}
      </div>

      <Footer />

      {/* Modals */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={handleAuthSuccess}
      />

      {token && (
        <MyInterestsModal
          isOpen={showInterestsModal}
          onClose={() => setShowInterestsModal(false)}
          token={token}
        />
      )}
    </main>
  );
}
