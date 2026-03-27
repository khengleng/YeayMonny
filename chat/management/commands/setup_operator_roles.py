from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create/update operator roles: Prompt Editor and Prompt Admin"

    def add_arguments(self, parser):
        parser.add_argument(
            "--editor-user",
            action="append",
            default=[],
            help="Username to add into Prompt Editor group (repeatable)",
        )
        parser.add_argument(
            "--admin-user",
            action="append",
            default=[],
            help="Username to add into Prompt Admin group (repeatable)",
        )

    def handle(self, *args, **options):
        editor_group = self._configure_group(
            group_name="Prompt Editor",
            permission_codenames=[
                "view_assistantconfig",
                "change_assistantconfig",
            ],
        )
        admin_group = self._configure_group(
            group_name="Prompt Admin",
            permission_codenames=[
                "view_assistantconfig",
                "change_assistantconfig",
                "manage_advanced_assistantconfig",
                "rollback_assistantconfig",
            ],
        )

        self._assign_users(editor_group, options["editor_user"])
        self._assign_users(admin_group, options["admin_user"])

        self.stdout.write(self.style.SUCCESS("Operator roles are ready."))

    def _configure_group(self, *, group_name: str, permission_codenames: list[str]) -> Group:
        group, _ = Group.objects.get_or_create(name=group_name)
        perms = list(Permission.objects.filter(codename__in=permission_codenames))
        found = {perm.codename for perm in perms}
        missing = sorted(set(permission_codenames) - found)
        if missing:
            raise CommandError(
                f"Missing permissions for {group_name}: {', '.join(missing)}. "
                "Run migrations first."
            )
        group.permissions.set(perms)
        return group

    def _assign_users(self, group: Group, usernames: list[str]) -> None:
        if not usernames:
            return

        user_model = get_user_model()
        for username in usernames:
            user = user_model.objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"User '{username}' not found")
            user.groups.add(group)
            self.stdout.write(f"Assigned '{username}' -> {group.name}")
