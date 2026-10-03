import React from "react";
import { Header } from "@/components/Header";
import { NewspaperHero } from "@/components/NewspaperHero";
import { NewsSection } from "@/components/NewsSection";
import { Footer } from "@/components/Footer";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col justify-between bg-paper-50 selection:bg-accent-red selection:text-white">
      <div>
        <Header />
        <NewspaperHero />
        <NewsSection />
      </div>
      <Footer />
    </main>
  );
}
