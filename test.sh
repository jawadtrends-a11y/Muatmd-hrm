#!/usr/bin/env bash
# تشغيل الحرّاس.
#
#   ./test.sh                     الكل بالتوازي على 4 عمّال (~4 دقائق)
#   ./test.sh tests/test_x.py     ملف محدد (تسلسلي — أسرع للواحد)
#   ./test.sh -1                  الكل تسلسليًا (للتشخيص)
#
# أربعة عمّال حدّ آمن: الخادم 7.7 جيجا، وكل عامل يفتح قاعدة اختبار
# مستقلة. و--dist loadfile يبقي اختبارات الملف على عامل واحد،
# فلا تتزاحم على نفس البيانات.

set -e
cd /opt/muatmd-hrm

# ── حارس التشغيل الواحد ───────────────────────────────────────
# تشغيلان متوازيان يسببان deadlock على pg_class، فتنهار مئات
# الاختبارات بأخطاء تهيئة لا علاقة لها بالكود. القفل يمنع الثاني
# بدل أن يفسد الأول.
exec 9>/tmp/muatmd-hrm-test.lock
if ! flock -n 9; then
    echo "⛔ هناك تشغيل جارٍ للحرّاس — انتظر انتهاءه." >&2
    exit 1
fi

# ── تنظيف قواعد الاختبار المتروكة ─────────────────────────────
# تبقى بعد انقطاع تشغيل سابق فتُربك كل تشغيل لاحق. تُحذف قبل
# البدء لا بعده — فالانقطاع لا يصل لما بعده أصلًا.
docker compose exec -T db psql -U hrm_app -d postgres -tAc \
    "select datname from pg_database where datname like 'test_%';" 2>/dev/null |
while read -r db; do
    [ -z "$db" ] && continue
    echo "🧹 حذف قاعدة اختبار متروكة: $db"
    docker compose exec -T db psql -U hrm_app -d postgres -c \
        "select pg_terminate_backend(pid) from pg_stat_activity where datname='$db';" >/dev/null 2>&1
    docker compose exec -T db psql -U hrm_app -d postgres -c \
        "DROP DATABASE IF EXISTS \"$db\";" >/dev/null 2>&1
done

if [ "$1" = "-1" ]; then
    shift
    exec docker compose exec -T -e DJANGO_DB_OWNER=1 web \
        pytest "${@:-tests/}" -q --no-header
fi

if [ $# -gt 0 ]; then
    exec docker compose exec -T -e DJANGO_DB_OWNER=1 web \
        pytest "$@" -q --no-header
fi

exec docker compose exec -T -e DJANGO_DB_OWNER=1 web \
    pytest tests/ -q --no-header -n 4 --dist loadfile
