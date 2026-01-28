from django.core.management.base import BaseCommand, CommandError
from app.services.secret_store import SecretStore, ensure_master_key


class Command(BaseCommand):
    help = "Set an encrypted secret key=value into the secrets store"

    def add_arguments(self, parser):
        parser.add_argument("keyvalue", type=str, help="Key=Value pair to set")
        parser.add_argument(
            "--persist-key",
            action="store_true",
            help="Write master key to file if missing",
        )

    def handle(self, *args, **options):
        kv = options["keyvalue"]
        if "=" not in kv:
            raise CommandError("Expected argument in form KEY=VALUE")
        k, v = kv.split("=", 1)
        if options.get("persist_key"):
            ensure_master_key(persist_to_file=True)
        store = SecretStore()
        try:
            store.set(k, v)
        except RuntimeError as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(f"Set secret {k}"))
