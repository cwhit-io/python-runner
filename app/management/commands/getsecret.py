from django.core.management.base import BaseCommand, CommandError
from app.services.secret_store import SecretStore


class Command(BaseCommand):
    help = "Get a secret value from the encrypted store (prints to stdout)"

    def add_arguments(self, parser):
        parser.add_argument("key", type=str, help="Secret key to retrieve")

    def handle(self, *args, **options):
        k = options["key"]
        store = SecretStore()
        try:
            v = store.get(k)
        except RuntimeError as e:
            raise CommandError(str(e))
        if v is None:
            raise CommandError(f"Secret {k} not found")
        self.stdout.write(v)
