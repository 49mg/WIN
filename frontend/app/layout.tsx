import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"] });
const body = IBM_Plex_Sans({ variable: "--font-body", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "WIN · What Is Next",
  description: "Tell WIN what you loved. Get what to watch, read or play next, with a reason for each pick.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${body.variable} font-sans antialiased`}>
        <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4">
          <header className="flex items-center justify-between py-5">
            <Link href="/" className="font-display text-2xl font-extrabold tracking-tight">
              WIN <span className="text-accent">→</span>
            </Link>
            <nav className="flex gap-5 text-sm text-muted">
              <Link href="/" className="hover:text-fg">Discover</Link>
              <Link href="/me" className="hover:text-fg">My taste &amp; queue</Link>
            </nav>
          </header>
          <main className="flex-1">{children}</main>
          <footer className="py-8 text-xs leading-relaxed text-muted">
            Data from <a className="underline" href="https://anilist.co">AniList</a>,{" "}
            <a className="underline" href="https://openlibrary.org">Open Library</a>,{" "}
            <a className="underline" href="https://rawg.io">RAWG</a> and{" "}
            <a className="underline" href="https://www.themoviedb.org">TMDB</a>. This product uses
            the TMDB API but is not endorsed or certified by TMDB.
          </footer>
        </div>
      </body>
    </html>
  );
}
