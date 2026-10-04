"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { NewspaperHeader } from "@/components/NewspaperHeader";
import { ArticleCard } from "@/components/ArticleCard";
import { AuthModal } from "@/components/AuthModal";
import { MyInterestsModal } from "@/components/MyInterestsModal";
import { Footer } from "@/components/Footer";
import {
  fetchCurrentUser,
  fetchSavedArticles,
  unsaveArticle,
} from "@/lib/api";
import { SavedArticleItem, User } from "@/types";
import { Bookmark, ArrowLeft, Trash2, ArrowRight } from "lucide-react";

export default function SavedArticlesPage() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [savedItems, setSavedItems] = useState<SavedArticleItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [showInterestsModal, setShowInterestsModal] = useState<boolean>(false);

  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token");
    if (savedToken) {
      setToken(savedToken);
      fetchCurrentUser(savedToken)
        .then(setUser)
        .catch(() => {});
      loadSaved(savedToken);
    } else {
      setLoading(false);
    }
  }, []);

  const loadSaved = async (authToken: string) => {
    setLoading(true);
    try {
      const resp = await fetchSavedArticles(authToken, 1, 50);
      setSavedItems(resp.items);
      setTotal(resp.total);
    } catch {
      setSavedItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (articleId: string) => {
    if (!token) return;
    try {
      await unsaveArticle(articleId, token);
      setSavedItems((prev) => prev.filter((item) => item.article.id !== articleId));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error("Failed to remove saved article", err);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-between bg-[#FAF8F5] text-[#181615]">
      <div>
        <NewspaperHeader
          user={user}
          onOpenAuth={() => setShowAuthModal(true)}
          onOpenInterests={() => setShowInterestsModal(true)}
          onSignOut={() => {
            localStorage.removeItem("pn_auth_token");
            setToken(null);
            setUser(null);
            setSavedItems([]);
            setTotal(0);
          }}
        />

        <main className="max-w-5xl mx-auto px-4 sm:px-8 py-8">
          {/* Top Bar */}
          <div className="flex items-center justify-between pb-4 mb-8 border-b-2 border-[#181615]">
            <div>
              <Link
                href="/newspaper"
                className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#7A7268] hover:text-[#181615] transition-colors mb-2"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Newspaper</span>
              </Link>
              <h1 className="font-editorial-heading font-black text-2xl sm:text-3xl lg:text-4xl text-[#181615]">
                Saved Stories
              </h1>
            </div>

            <span className="text-xs font-sans text-[#7A7268]">
              {total} {total === 1 ? "story saved" : "stories saved"}
            </span>
          </div>

          {!token ? (
            <div className="p-8 sm:p-12 text-center bg-white border border-[#DCD3C7] my-8 font-sans">
              <Bookmark className="w-12 h-12 text-[#8C2524] mx-auto mb-4" />
              <h2 className="text-xl font-bold text-[#181615] mb-2">Sign in to view saved stories</h2>
              <p className="text-sm text-[#7A7268] mb-6">
                Your saved articles are synced to your account so you can read them at your convenience.
              </p>
              <button
                onClick={() => setShowAuthModal(true)}
                className="px-6 py-2.5 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors"
              >
                Sign In / Register
              </button>
            </div>
          ) : loading ? (
            <div className="space-y-4 animate-pulse">
              {[1, 2, 3].map((n) => (
                <div key={n} className="h-32 bg-[#E5DDD0] rounded-sm" />
              ))}
            </div>
          ) : savedItems.length === 0 ? (
            <div className="p-8 sm:p-12 text-center bg-white border border-[#DCD3C7] my-8 font-sans">
              <Bookmark className="w-12 h-12 text-[#DCD3C7] mx-auto mb-4" />
              <h2 className="text-xl font-bold text-[#181615] mb-2">Your reading list is empty</h2>
              <p className="text-sm text-[#7A7268] mb-6">
                Bookmark articles while browsing your personalized newspaper to read them later.
              </p>
              <Link
                href="/newspaper"
                className="px-6 py-2.5 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors inline-flex items-center gap-2"
              >
                <span>Browse Today's Edition</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          ) : (
            <div className="space-y-6">
              {savedItems.map((item) => (
                <div
                  key={item.id}
                  className="bg-white border border-[#E4DCCF] p-4 sm:p-6 flex flex-col sm:flex-row gap-6 items-start justify-between group hover:border-[#181615] transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 text-xs text-[#8C2524] font-bold uppercase tracking-wider mb-1 font-sans">
                      {item.article.topics.length > 0 && (
                        <span>{item.article.topics[0].name}</span>
                      )}
                      <span>•</span>
                      <span className="text-[#7A7268] font-normal">
                        Saved on {new Date(item.saved_at).toLocaleDateString()}
                      </span>
                    </div>

                    <Link href={`/article/${item.article.id}`}>
                      <h3 className="font-editorial-heading font-bold text-xl text-[#181615] group-hover:text-[#8C2524] transition-colors leading-snug">
                        {item.article.title}
                      </h3>
                    </Link>

                    {item.article.description && (
                      <p className="font-editorial-body text-sm text-[#4E473F] mt-2 line-clamp-2">
                        {item.article.description}
                      </p>
                    )}
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-3 pt-3 sm:pt-0 border-t sm:border-t-0 border-[#EFE9DF] shrink-0 font-sans">
                    <Link
                      href={`/article/${item.article.id}`}
                      className="px-4 py-2 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors inline-flex items-center gap-1.5"
                    >
                      <span>Read</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>

                    <button
                      onClick={() => handleRemove(item.article.id)}
                      className="text-xs text-rose-700 hover:text-rose-900 font-semibold inline-flex items-center gap-1 p-1"
                      title="Remove from saved"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Remove</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      <Footer />

      {/* Auth Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={(newToken, newUser) => {
          localStorage.setItem("pn_auth_token", newToken);
          setToken(newToken);
          setUser(newUser);
          setShowAuthModal(false);
          loadSaved(newToken);
        }}
      />

      {token && (
        <MyInterestsModal
          isOpen={showInterestsModal}
          onClose={() => setShowInterestsModal(false)}
          token={token}
        />
      )}
    </div>
  );
}
