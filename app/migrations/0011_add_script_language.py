# Generated manually for adding language field to Script model

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0010_userprofile_time_format_userprofile_timezone"),
    ]

    operations = [
        migrations.AddField(
            model_name="script",
            name="language",
            field=models.CharField(
                choices=[("python", "Python"), ("bash", "Bash")],
                default="python",
                help_text="Script language/runtime",
                max_length=20,
            ),
        ),
    ]
