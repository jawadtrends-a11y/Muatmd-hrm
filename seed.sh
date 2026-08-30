#!/bin/bash
# بذر البيانات التجريبية — ./seed.sh أو ./seed.sh --reset
cd /opt/muatmd-hrm && docker compose exec -T -e DJANGO_DB_OWNER=1 web python manage.py seed_demo "$@"
