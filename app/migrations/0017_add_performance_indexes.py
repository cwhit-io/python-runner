# Generated migration for performance indexes on PostgreSQL

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('app', '0016_alter_scriptexecution_trigger_type'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='script',
            index=models.Index(fields=['expose_to_mcp'], name='script_expose_mcp_idx'),
        ),
        migrations.AddIndex(
            model_name='script',
            index=models.Index(fields=['is_public'], name='script_is_public_idx'),
        ),
        migrations.AddIndex(
            model_name='scriptexecution',
            index=models.Index(fields=['script', 'status'], name='scriptexec_script_status_idx'),
        ),
        migrations.AddIndex(
            model_name='scriptexecution',
            index=models.Index(fields=['started_at'], name='scriptexec_started_at_idx'),
        ),
        migrations.AddIndex(
            model_name='scriptexecution',
            index=models.Index(fields=['completed_at'], name='scriptexec_completed_at_idx'),
        ),
        migrations.AddIndex(
            model_name='scriptexecution',
            index=models.Index(fields=['-created_at', 'status'], name='scriptexec_created_status_idx'),
        ),
        migrations.AddIndex(
            model_name='scriptschedule',
            index=models.Index(fields=['is_active'], name='scriptschedule_active_idx'),
        ),
        migrations.AddIndex(
            model_name='scriptschedule',
            index=models.Index(fields=['next_run'], name='scriptschedule_next_run_idx'),
        ),
        migrations.AddIndex(
            model_name='scriptschedule',
            index=models.Index(fields=['script', 'is_active'], name='scriptschedule_script_active_idx'),
        ),
    ]