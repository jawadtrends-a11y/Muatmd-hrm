"""
بذر بيانات المنصة — يُشغَّل عند كل نشر.

آمن للتكرار: يزامن ولا يكرّر. الأدوار تُنسخ للحسابات عند إنشائها
لا هنا، لأن كل حساب يملك نسخته.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "يزامن المزايا والباقات وأحداث الإشعارات وقوالبها"

    def handle(self, *args, **options):
        from apps.accounts.services.plans import (
            sync_default_plans, sync_feature_registry,
        )
        from apps.notifications.services.templates import sync_default_templates
        from apps.notifications.catalog import EVENTS
        from apps.notifications.models import NotificationEvent

        n = sync_feature_registry()
        self.stdout.write(f"المزايا: {n}")

        plans = sync_default_plans()
        self.stdout.write(f"الباقات: {plans}")

        for i, spec in enumerate(EVENTS):
            NotificationEvent.objects.update_or_create(
                event_key=spec.key,
                defaults={
                    "module": spec.module, "name_ar": spec.name_ar,
                    "default_channels": list(spec.channels),
                    "is_mandatory": spec.is_mandatory, "sort_order": i,
                },
            )
        self.stdout.write(f"أحداث الإشعارات: {NotificationEvent.objects.count()}")

        t = sync_default_templates()
        self.stdout.write(f"قوالب الإشعارات: {t['templates']}")
        self.stdout.write(self.style.SUCCESS("اكتمل بذر المنصة"))
