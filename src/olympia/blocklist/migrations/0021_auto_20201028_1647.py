# Generated by Django 2.2.16 on 2020-10-28 16:47

from django.db import migrations
import olympia.versions.fields


class Migration(migrations.Migration):

    dependencies = [
        ('blocklist', '0020_auto_20200923_1808'),
    ]

    operations = [
        migrations.AlterField(
            model_name='block',
            name='max_version',
            field=olympia.versions.fields.VersionStringField(default='*', max_length=255),
        ),
        migrations.AlterField(
            model_name='block',
            name='min_version',
            field=olympia.versions.fields.VersionStringField(default='0', max_length=255),
        ),
        migrations.AlterField(
            model_name='blocklistsubmission',
            name='max_version',
            field=olympia.versions.fields.VersionStringField(default='*', max_length=255),
        ),
        migrations.AlterField(
            model_name='blocklistsubmission',
            name='min_version',
            field=olympia.versions.fields.VersionStringField(default='0', max_length=255),
        ),
    ]
