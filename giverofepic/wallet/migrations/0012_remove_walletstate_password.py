# Generated by Django 4.1.3 on 2022-11-26 15:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0011_rename_directory_walletstate_wallet_dir'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='walletstate',
            name='password',
        ),
    ]
