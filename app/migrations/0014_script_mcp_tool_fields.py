# Generated migration for MCP tool dynamic generation fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0013_globalcredentials_and_mcp_exposure'),
    ]

    operations = [
        migrations.AddField(
            model_name='script',
            name='mcp_tool_name',
            field=models.CharField(
                blank=True,
                max_length=100,
                help_text='Custom name for the MCP tool (lowercase snake_case, auto-generated from script name if empty)'
            ),
        ),
        migrations.AddField(
            model_name='script',
            name='input_schema',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text='JSON schema for script input parameters (auto-generated if empty)'
            ),
        ),
        migrations.AddField(
            model_name='script',
            name='is_destructive',
            field=models.BooleanField(
                default=False,
                help_text='Mark this script as destructive/making changes (for safety warnings)'
            ),
        ),
    ]