from django.core.management.base import BaseCommand, CommandError
from app.services.secret_store import SecretStore


class Command(BaseCommand):
    help = "List secret keys stored in the encrypted store"

    def handle(self, *args, **options):
        store = SecretStore()
        try:
            names = store.list_names()
        except RuntimeError as e:
            raise CommandError(str(e))
        for n in names:
            self.stdout.write(n)
