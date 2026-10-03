import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Personalized Newspaper — Your news. Your interests.",
  description:
    "A personal daily newspaper application that ingests web news, understands user interests, and generates a personalized news edition.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-paper-50 text-ink min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
