from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.attendance"
    label = "attendance"

    def ready(self):
        # ⚠️ ق-٢٦٢: إشارات تُعيد احتساب الأيّام عند كل حدثٍ يمسّ الماضي —
        # عطلةٌ تُضاف، أو **إجازةٌ تُعتمد بعد يومين** فتترك أيّامها غيابًا.
        from apps.attendance import signals
        signals.register()
