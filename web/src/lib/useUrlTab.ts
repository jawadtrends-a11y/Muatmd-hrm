"use client";
/**
 * التبويب في الرابط — خُطّافٌ واحدٌ لكل الصفحات (ق-231).
 *
 * ⚠️⚠️ **والتحديث كان يُعيد للتبويب الأول** (بلاغ جواد): فالتبويب في
 * الذاكرة وحدها. وأُصلح في ثلاث صفحاتٍ **كلٌّ بطريقة** — فعادت العلّة
 * في إحدى عشرة: **فلا شيء يُلزم الصفحة الجديدة بالحلّ**.
 *
 * - يُقرأ **بعد التحميل** لا عند التصيير: فالخادم لا يعرف الرابط،
 *   وقراءته عند التصيير تُنتج صفحتين مختلفتين (hydration)
 * - ⚠️ ويحفظ `history.state` — **ففيه حالة Next.js**، ومحوُها يُربك
 *   زرّ الرجوع
 * - وقيمةٌ في الرابط ليست من التبويبات تُتجاهل — فلا تبويبَ فارغ
 * - والافتراضيّ لا يُكتب — فالرابط يبقى نظيفًا
 */
import { useCallback, useEffect, useState } from "react";

export function useUrlTab<T extends string>(
  tabs: readonly T[], initial: T, param = "tab",
): [T, (t: T) => void] {
  const [tab, setTabState] = useState<T>(initial);

  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get(param);
    if (v && (tabs as readonly string[]).includes(v)) setTabState(v as T);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setTab = useCallback((t: T) => {
    setTabState(t);
    const u = new URL(window.location.href);
    if (t === initial) u.searchParams.delete(param);
    else u.searchParams.set(param, t);
    window.history.replaceState(window.history.state, "", u.toString());
  }, [initial, param]);

  return [tab, setTab];
}
