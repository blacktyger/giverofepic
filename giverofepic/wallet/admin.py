from django.contrib import admin

from wallet.models import UserIP, Transaction, Wallet, EpicBoxAddress

admin.site.register((Wallet, Transaction, UserIP, EpicBoxAddress))