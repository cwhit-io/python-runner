from django.core.management.base import BaseCommand, CommandError
from app.services.secret_store import SecretStore


class Command(BaseCommand):
    help = "Delete a secret from the encrypted store"

    def add_arguments(self, parser):
        parser.add_argument("key", type=str, help="Secret key to delete")

    def handle(self, *args, **options):
        k = options["key"]
        store = SecretStore()
        try:
            ok = store.delete(k)
        except RuntimeError as e:
            raise CommandError(str(e))
        if not ok:
            raise CommandError(f"Secret {k} not found")
        self.stdout.write(self.style.SUCCESS(f"Deleted secret {k}"))
