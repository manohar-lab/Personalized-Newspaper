"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Onboarding } from "@/components/Onboarding";
import { fetchCurrentUser } from "@/lib/api";
import { User } from "@/types";
import { ArrowLeft } from "lucide-react";

export default function OnboardingPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const savedToken = localStorage.getItem("pn_auth_token");
    if (!savedToken) {
      router.push("/login");
      return;
    }
    setToken(savedToken);
    fetchCurrentUser(savedToken)
      .then((u) => {
        setUser(u);
        setLoading(false);
      })
      .catch(() => {
        localStorage.removeItem("pn_auth_token");
        router.push("/login");
      });
  }, [router]);

  const handleComplete = () => {
    router.push("/newspaper");
  };

  if (loading || !token) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center font-sans text-xs text-[#7A7268]">
        Loading your preference curator...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FAF8F5] py-12 px-4 sm:px-8 font-sans text-[#181615]">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <Link
            href="/newspaper"
            className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#7A7268] hover:text-[#181615]"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Skip to Newspaper</span>
          </Link>
        </div>

        <div className="bg-white border-2 border-[#181615] p-6 sm:p-10 shadow-sm">
          <Onboarding
            token={token}
            onComplete={handleComplete}
          />
        </div>
      </div>
    </div>
  );
}
