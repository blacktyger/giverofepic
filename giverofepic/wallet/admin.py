from django.contrib import admin

from wallet.models import *

admin.site.register((WalletState, Transaction, WalletAddress, IPAddress))