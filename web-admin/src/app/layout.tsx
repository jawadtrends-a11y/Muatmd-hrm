import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic } from "next/font/google";
import AdminShell from "@/components/AdminShell";
import "./globals.css";

const plex = IBM_Plex_Sans_Arabic({
  variable: "--font-plex",
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "لوحة معتمد",
  description: "لوحة إدارة منصة معتمد HR",
  robots: { index: false, follow: false, nocache: true },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ar" dir="rtl" data-theme="light" className={plex.variable}>
      <body>
        <AdminShell>{children}</AdminShell>
      </body>
    </html>
  );
}
