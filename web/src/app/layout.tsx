import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic } from "next/font/google";
import AppShell from "@/components/AppShell";
import "./globals.css";

const plex = IBM_Plex_Sans_Arabic({
  variable: "--font-plex",
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "معتمد HR — نظام الموارد البشرية",
  description: "نظام موارد بشرية متكامل متوافق مع نظام العمل السعودي",
};

const BOOT = `(function(){try{
  var p=JSON.parse(localStorage.getItem('muatmd_prefs')||'{}');
  var lang=p.lang==='en'?'en':'ar';
  var dark=p.theme==='dark'||(p.theme==='auto'&&
    window.matchMedia('(prefers-color-scheme: dark)').matches);
  var h=document.documentElement;
  h.lang=lang; h.dir=lang==='ar'?'rtl':'ltr';
  h.setAttribute('data-theme',dark?'dark':'light');
}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="ar"
      dir="rtl"
      data-theme="light"
      className={plex.variable}
      suppressHydrationWarning
    >
      <body>
        {/* يمنع ومضة الوضع الخاطئ قبل تحميل React */}
        <script dangerouslySetInnerHTML={{ __html: BOOT }} />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
