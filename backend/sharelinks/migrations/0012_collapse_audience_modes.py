from django.db import migrations, models


def collapse_audience_modes(apps, schema_editor):
    """Drop the org/collaborators audiences; existing rows become allowlist links."""
    ShareLink = apps.get_model('sharelinks', 'ShareLink')
    ShareLink.objects.filter(audience_mode__in=['org', 'collaborators']).update(audience_mode='allowlist')


class Migration(migrations.Migration):

    dependencies = [
        ('sharelinks', '0011_sharelink_audience_emails_sharelink_audience_mode'),
    ]

    operations = [
        migrations.RunPython(collapse_audience_modes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='sharelink',
            name='audience_mode',
            field=models.CharField(
                choices=[('anyone', 'Anyone with the link'), ('allowlist', 'Email allowlist')],
                default='anyone',
                max_length=20,
            ),
        ),
    ]
