from django.conf import settings
from django.db import models


class AdminToolUsage(models.Model):
    """
    Tracks usage of Wagtail admin tools/pages so the team can see which
    tools are used most. Logged via JS on admin pages (see wagtail_hooks.py
    and the admin-tool-usage view in views.py).

    Intentionally minimal: no dashboards/reporting are built on top of this
    yet (see issue #311). The fields here are enough to support building
    those later (e.g. counts per tool, per user, over time).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_tool_usages",
    )
    tool = models.CharField(
        max_length=255,
        help_text="Identifier for the admin tool/page, e.g. its path.",
    )
    action = models.CharField(
        max_length=255,
        blank=True,
        help_text="What was done, e.g. the id/label of the button clicked. Blank for a plain page view.",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["timestamp"]),
        ]
        verbose_name = "Admin Tool Usage"
        verbose_name_plural = "Admin Tool Usage Records"

    def __str__(self):
        who = self.user.username if self.user_id else "anonymous"
        return f"{who} used {self.tool} ({self.action}) at {self.timestamp:%Y-%m-%d %H:%M}"
