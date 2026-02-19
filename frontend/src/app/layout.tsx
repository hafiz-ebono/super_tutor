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
      <head>
        <link rel="stylesheet" href="https://oat.ink/oat.min.css" />
      </head>
      <body>
        <header className="site-header">
          <Link href="/" className="site-header-logo">
            Super Tutor
          </Link>
          <Link
            href="/create"
            className="btn btn-primary"
            style={{ fontSize: "var(--text-1)", padding: "var(--space-2) var(--space-4)" }}
          >
            New session →
          </Link>
        </header>
        {children}
      </body>
    </html>
  );
}
