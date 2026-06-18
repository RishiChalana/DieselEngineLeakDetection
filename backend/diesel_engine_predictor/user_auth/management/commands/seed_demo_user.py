from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    """Idempotently ensures a fixed demo account exists. Safe to run on
    every container startup — uses get_or_create so it never duplicates
    or errors if the user already exists."""
    help = "Seed a permanent demo account for the live deployment"

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={"email": "demo@leakguard.local"},
        )
        if created:
            user.set_password("demo12345")
            user.save()
            self.stdout.write("Demo user created")
        else:
            self.stdout.write("Demo user already exists")
        Token.objects.get_or_create(user=user)
