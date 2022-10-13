# Generated by Django 3.2.13 on 2022-10-12 19:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import signoffs.core.models.signets


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Signet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signoff_id', models.CharField(max_length=100, validators=[signoffs.core.models.signets.validate_signoff_id], verbose_name='Signoff Type')),
                ('sigil', models.CharField(max_length=256, verbose_name='Signed By')),
                ('sigil_label', models.CharField(max_length=256, null=True)),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['timestamp'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RevokedSignet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, editable=False, verbose_name='Revoked at')),
                ('signet', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='revoked', to='signoffs_signets.signet')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Revoked by')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
