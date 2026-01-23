from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from app.models import UserProfile


class Command(BaseCommand):
    help = 'Create UserProfile for all users who don\'t have one'

    def handle(self, *args, **options):
        users_without_profile = []
        
        for user in User.objects.all():
            profile, created = UserProfile.objects.get_or_create(user=user)
            if created:
                users_without_profile.append(user.username)
        
        if users_without_profile:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created profiles for {len(users_without_profile)} users: {", ".join(users_without_profile)}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles!')
            )
