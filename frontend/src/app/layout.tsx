import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Super Tutor",
  description: "Turn any article into a complete study session",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <header className="sticky top-0 z-50 bg-white border-b border-zinc-100 px-5 h-14 flex items-center justify-between">
          <Link href="/" className="font-bold text-zinc-900 tracking-tight">
            Super Tutor
          </Link>
          <Link
            href="/create"
            className="text-sm font-medium bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
          >
            New session →
          </Link>
        </header>
        {children}
        <footer className="border-t border-zinc-100 py-4 text-center text-xs text-zinc-400">
          Made with ♥ by{" "}
          <a
            href="https://www.linkedin.com/in/hafiz408/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-500 hover:text-blue-600 transition-colors"
          >
            Hafiz
          </a>
          {" "}· 2026
        </footer>
      </body>
    </html>
  );
}
