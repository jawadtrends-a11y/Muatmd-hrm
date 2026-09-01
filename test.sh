#!/usr/bin/env bash
# تشغيل الحرّاس.
#
#   ./test.sh                     الكل بالتوازي على 4 عمّال (~2 دقيقة)
#   ./test.sh tests/test_x.py     ملف محدد (تسلسلي — أسرع للواحد)
#   ./test.sh -1                  الكل تسلسليًا (للتشخيص)
#
# أربعة عمّال حدّ آمن: الخادم 7.7 جيجا، وكل عامل يفتح قاعدة اختبار
# مستقلة. و--dist loadfile يبقي اختبارات الملف على عامل واحد،
# فلا تتزاحم على نفس البيانات.

set -e
cd /opt/muatmd-hrm

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
