# Generated by Django 4.1.3 on 2023-02-17 11:27

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('giveaway', '0005_alter_link_currency_alter_link_event_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='link',
            name='expires',
            field=models.DateTimeField(default=datetime.datetime(2023, 2, 17, 12, 27, 51, 264210, tzinfo=datetime.timezone.utc)),
        ),
    ]
