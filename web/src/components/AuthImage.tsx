"use client";

import { useEffect, useState } from "react";

import { getToken } from "@/lib/api";

/**
 * صورةٌ من مسارٍ محميّ.
 *
 * ⚠️⚠️ **`<img src>` لا يُرسل رأس `Authorization` أبدًا.** والمصادقة عندنا
 * برمز `Bearer`، فكل صورةٍ من `/api/files/<id>/` تُطلب **بلا رمز** فيردّ
 * الخادم ٤٠١ — **وتظهر مكسورة**. وهي علّةٌ تمسّ كل صورة: الشعار وصور
 * الموظفين والوثائق.
 *
 * فتُجلب هنا بـ`fetch` (ومعها الرمز)، وتُحوّل إلى `blob:` يقرؤه المتصفح.
 * ⚠️ **ويُحرَّر العنوان عند الخروج** — وإلا تسرّبت الذاكرة مع كل تنقّل.
 */
export default function AuthImage({
  src, alt, style, className,
}: {
  src: string;
  alt: string;
  style?: React.CSSProperties;
  className?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let revoked: string | null = null;
    let alive = true;

    (async () => {
      try {
        const base = process.env.NEXT_PUBLIC_API_BASE || "/api";
        const path = src.startsWith("/api/") ? src.slice(4) : src;
        const t = getToken();
        const res = await fetch(`${base}${path}`, {
          headers: t ? { Authorization: `Bearer ${t}` } : {},
          credentials: "include",
        });
        if (!res.ok) return;
        const blob = await res.blob();
        if (!alive) return;
        revoked = URL.createObjectURL(blob);
        setUrl(revoked);
      } catch {
        /* تُترك فارغةً — ولا تُكسر الصفحة */
      }
    })();

    return () => {
      alive = false;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [src]);

  if (!url) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={alt} style={style} className={className} />;
}
