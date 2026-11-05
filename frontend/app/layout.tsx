import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";
import { Nav } from "@/components/Nav";
import { UserProvider } from "@/lib/user";
import "./globals.css";

const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"] });
const body = IBM_Plex_Sans({ variable: "--font-body", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  // absolute URLs for link previews (taste cards); set SITE_URL to the real domain when deployed
  metadataBase: new URL(process.env.SITE_URL ?? "http://localhost:3000"),
  title: "WIN · What Is Next",
  description: "Tell WIN what you loved. Get what to watch, read or play next, with a reason for each pick.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${body.variable} font-sans antialiased`}>
        <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 sm:px-6">
          <header className="flex flex-wrap items-center justify-between gap-3 py-5">
            <Link href="/" className="flex items-baseline gap-2" aria-label="WIN, what is next: home">
              <span className="font-display text-3xl font-extrabold tracking-tight">WIN</span>
              <span className="hidden text-sm text-muted sm:inline">what is next</span>
            </Link>
            <Nav />
          </header>
          <main className="flex-1">
            <UserProvider>{children}</UserProvider>
          </main>
          <footer className="mt-16 flex flex-col gap-3 border-t border-line py-8 text-xs leading-relaxed text-muted sm:flex-row sm:items-center sm:gap-5">
            <a href="https://www.themoviedb.org" className="shrink-0" aria-label="The Movie Database (TMDB)">
              {/* eslint-disable-next-line @next/next/no-img-element -- official TMDB logo, required attribution */}
              <img src="/tmdb.svg" alt="TMDB logo" className="h-3" />
            </a>
            <p>
              Data from <a className="underline" href="https://anilist.co">AniList</a>,{" "}
              <a className="underline" href="https://openlibrary.org">Open Library</a>,{" "}
              <a className="underline" href="https://www.igdb.com">IGDB</a> and{" "}
              <a className="underline" href="https://www.themoviedb.org">TMDB</a>. This product uses
              the TMDB API but is not endorsed or certified by TMDB.{" "}
              <Link className="underline" href="/stats">
                How well does WIN work?
              </Link>
            </p>
          </footer>
        </div>
      </body>
    </html>
  );
}
