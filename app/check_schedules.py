#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

from app.models import ScriptSchedule

schedules = ScriptSchedule.objects.all()
print(f"Total schedules: {schedules.count()}\n")

for s in schedules:
    print(f"ID: {s.id}")  # type: ignore
    print(f"  Name: {s.name}")
    print(f"  Type: {s.schedule_type}")
    print(f"  Active: {s.is_active}")
    if s.schedule_type == "interval":
        print(f"  Start: {s.start_datetime}")
        print(f"  Interval: {s.interval_value} {s.interval_unit}")
    elif s.schedule_type == "single":
        print(f"  Start: {s.start_datetime}")
    elif s.schedule_type == "cron":
        print(f"  Cron: {s.cron_expression}")
    print()
