# Generated by Django 4.1.3 on 2022-11-25 16:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0006_rename_wallet_walletstate'),
    ]

    operations = [
        migrations.AddField(
            model_name='walletstate',
            name='directory',
            field=models.CharField(default='C:\\Users\\%USERPROFILE%\\.epic\\main', max_length=128),
        ),
        migrations.AlterField(
            model_name='walletstate',
            name='name',
            field=models.CharField(default='epic_wallet', max_length=128),
        ),
    ]
