"use client";

import React, { useState } from "react";
import { loginUser, registerUser } from "@/lib/api";
import { User } from "@/types";
import { X, Lock, Mail, User as UserIcon, AlertCircle } from "lucide-react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthSuccess: (token: string, user: User) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onAuthSuccess,
}) => {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "register") {
        if (!email || !password) {
          setError("Email and password are required.");
          setLoading(false);
          return;
        }
        if (password.length < 8) {
          setError("Password must be at least 8 characters long.");
          setLoading(false);
          return;
        }
        const data = await registerUser(email, password, fullName || undefined);
        onAuthSuccess(data.access_token, data.user);
      } else {
        const data = await loginUser(email, password);
        onAuthSuccess(data.access_token, data.user);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-[#FAF9F5] border-2 border-[#121212] shadow-[8px_8px_0px_0px_rgba(18,18,18,1)] p-6 font-serif">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#121212] hover:opacity-75 transition-opacity"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center mb-6">
          <span className="text-xs font-sans tracking-widest uppercase text-[#8C8275] border-b border-[#D3CBB9] pb-1">
            Account Access
          </span>
          <h2 className="text-2xl font-bold uppercase tracking-tight text-[#121212] mt-2">
            {mode === "register" ? "Create Account" : "Sign In"}
          </h2>
          <p className="text-sm text-[#4A453E] font-sans mt-1">
            {mode === "register"
              ? "Join to personalize your daily news edition."
              : "Welcome back to your personalized newspaper."}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-300 text-red-800 text-sm font-sans flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 font-sans">
          {mode === "register" && (
            <div>
              <label className="block text-xs font-semibold text-[#121212] uppercase mb-1">
                Full Name
              </label>
              <div className="relative">
                <UserIcon className="w-4 h-4 absolute left-3 top-3 text-[#8C8275]" />
                <input
                  type="text"
                  placeholder="Jane Doe"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-[#D3CBB9] focus:outline-none focus:border-[#121212]"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-[#121212] uppercase mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3 top-3 text-[#8C8275]" />
              <input
                type="email"
                required
                placeholder="reader@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-[#D3CBB9] focus:outline-none focus:border-[#121212]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#121212] uppercase mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-3 text-[#8C8275]" />
              <input
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-[#D3CBB9] focus:outline-none focus:border-[#121212]"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 mt-2 bg-[#121212] text-white font-sans text-xs font-bold uppercase tracking-wider hover:bg-[#2A2A2A] transition-colors border border-[#121212]"
          >
            {loading
              ? "Processing..."
              : mode === "register"
              ? "Create Account & Onboard"
              : "Sign In"}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-[#D3CBB9] text-center font-sans text-xs text-[#4A453E]">
          {mode === "register" ? (
            <p>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("login");
                  setError(null);
                }}
                className="font-bold text-[#121212] underline uppercase hover:opacity-75"
              >
                Sign In
              </button>
            </p>
          ) : (
            <p>
              Need an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("register");
                  setError(null);
                }}
                className="font-bold text-[#121212] underline uppercase hover:opacity-75"
              >
                Create Account
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
