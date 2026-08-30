#!/bin/bash
# تشغيل الحرّاس — ./test.sh أو ./test.sh tests/test_payroll_engine.py
cd /opt/muatmd-hrm && docker compose exec -T -e DJANGO_DB_OWNER=1 web pytest "${@:-tests/}" -q --no-header
