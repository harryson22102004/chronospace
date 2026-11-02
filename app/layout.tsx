import type { Metadata } from "next";
import { Fraunces, Outfit } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";

const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });
const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces" });

export const metadata: Metadata = {
  title: "ChronoSpace",
  description: "An evidence-aware spatial memory. A photograph you can step into, with observation, estimation, generation, and recollection kept apart.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} ${fraunces.variable} antialiased`}>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
