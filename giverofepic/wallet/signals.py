from django.db.models.signals import pre_save
from django.dispatch import receiver

from wallet.models import WalletState


@receiver(pre_save, sender=WalletState)
def toggle_wallet_instance(sender, instance, **kwargs):
    try:
        obj = sender.objects.get(id=instance.id)
    except sender.DoesNotExist:
        # Object is new, so field hasn't technically changed, but you may want to do something else here.
        pass
    else:
        if not obj.disabled == instance.disabled:
            if instance.disabled:
                print(f'STOPPING {instance.name} WALLET RELATED PROCESSES')
            else:
                print(f'STARTING {instance.name} WALLET AND ITS RELATED PROCESSES')
