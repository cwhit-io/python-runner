"""Add schedule_type and calendar_expression to ScriptSchedule

Revision ID: 0007_add_schedule_type
Revises: 0006_tag_script_tags
Create Date: 2026-01-28 00:00:00.000000
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0006_tag_script_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="scriptschedule",
            name="schedule_type",
            field=models.CharField(
                choices=[
                    ("cron", "Cron"),
                    ("single", "Single datetime"),
                    ("rrule", "Recurring rule (RRULE)"),
                ],
                default="cron",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="scriptschedule",
            name="calendar_expression",
            field=models.TextField(default="", blank=True),
        ),
    ]
