# Generated by Django 4.1.3 on 2023-02-15 16:09

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('giveaway', '0002_alter_link_address_alter_link_event_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='link',
            old_name='short_link',
            new_name='ready_link',
        ),
        migrations.AddField(
            model_name='link',
            name='code',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='link',
            name='expires',
            field=models.DateTimeField(default=datetime.datetime(2023, 2, 15, 16, 10, 28, 327295, tzinfo=datetime.timezone.utc)),
        ),
    ]
