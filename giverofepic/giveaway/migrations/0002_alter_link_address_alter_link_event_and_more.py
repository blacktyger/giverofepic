# Generated by Django 4.1.3 on 2023-02-09 20:56

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('giveaway', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='link',
            name='address',
            field=models.CharField(blank=True, help_text='receiver wallet address', max_length=128),
        ),
        migrations.AlterField(
            model_name='link',
            name='event',
            field=models.CharField(default='giveaway', max_length=64),
        ),
        migrations.AlterField(
            model_name='link',
            name='expires',
            field=models.DateTimeField(default=datetime.datetime(2023, 2, 9, 20, 57, 8, 744101, tzinfo=datetime.timezone.utc)),
        ),
    ]