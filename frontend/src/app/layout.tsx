import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ScorePilot AI — Intelligent Academic Evaluation",
  description:
    "The future operating system for AI-powered academic evaluation. Transform grading with intelligent OCR extraction, semantic scoring, and explainable AI analytics.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} dark h-full antialiased scroll-smooth`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
