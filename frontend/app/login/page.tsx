"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { loginUser } from "@/lib/api";
import { ArrowLeft, Lock, Mail, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const resp = await loginUser(email, password);
      localStorage.setItem("pn_auth_token", resp.access_token);
      router.push("/newspaper");
    } catch (err: any) {
      setError(err?.message || "Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF8F5] flex flex-col justify-center py-12 sm:px-6 lg:px-8 font-sans text-[#181615]">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <Link
          href="/newspaper"
          className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#7A7268] hover:text-[#181615] mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Newspaper</span>
        </Link>
        <h1 className="font-editorial-heading font-black text-3xl sm:text-4xl text-[#181615]">
          Sign In
        </h1>
        <p className="mt-2 text-sm text-[#6C645C] font-editorial-body italic">
          Access your personalized daily edition
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white border-2 border-[#181615] py-8 px-6 sm:px-10 shadow-sm">
          {error && (
            <div className="mb-6 p-3 bg-rose-50 border border-rose-300 text-rose-800 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#181615] mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-[#8C847B] absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="reader@example.com"
                  className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-[#DCD3C7] rounded-none focus:outline-none focus:border-[#181615]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#181615] mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[#8C847B] absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-[#DCD3C7] rounded-none focus:outline-none focus:border-[#181615]"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#181615] text-[#FAF8F5] text-xs font-bold uppercase tracking-wider hover:bg-[#8C2524] transition-colors disabled:opacity-50"
            >
              {loading ? "Authenticating..." : "Sign In to Newspaper"}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-[#EFE9DF] text-center text-xs text-[#7A7268]">
            Don't have an account?{" "}
            <Link href="/register" className="font-bold text-[#8C2524] hover:underline">
              Register now
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
