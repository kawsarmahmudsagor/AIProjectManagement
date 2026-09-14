import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { parseThemeCookie, themeDataAttr, THEME_COOKIE } from "@/lib/theme";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Project Management",
  description: "Upload a document, let AI draft your project entry, review, export.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // Read server-side (this app already reads cookies server-side for auth via
  // requireSession()) so the theme is correct on the very first byte — no blocking
  // inline script, no hydration mismatch, no flash. "system" omits the attribute
  // entirely so globals.css's `@media (prefers-color-scheme: dark)` block decides
  // instead of pinning either theme (see lib/theme.ts's themeDataAttr).
  const jar = await cookies();
  const dataTheme = themeDataAttr(parseThemeCookie(jar.get(THEME_COOKIE)?.value));

  return (
    <html
      lang="en"
      data-theme={dataTheme}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-canvas text-ink">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
