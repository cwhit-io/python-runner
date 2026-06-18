#!/usr/bin/env python3
"""
Management command to inline shared utils and install AI wrapper scripts
into the ScriptDash database.

Usage:
    python manage.py install_ai_wrappers [--owner USERNAME]
"""

import json
import os
import re
import ast
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from app.models import Script


SERVICES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "ai_scripts"
)
SHARED_PATH = os.path.join(SERVICES_DIR, "shared", "wrapper_utils.py")

# Services that need planning_center_request
PLANNING_CENTER_SERVICES = {
    "planning_center_people",
    "planning_center_calendar",
    "planning_center_services",
    "planning_center_publishing",
    "planning_center_giving",
    "planning_center_groups",
    "planning_center_registrations",
    "planning_center_checkins",
}

# Services that need simple_api_request
SIMPLE_API_SERVICES = {"vimeo", "emailoctopus", "sermonshots", "wordpress"}

SERVICE_CONFIGS = {
    "planning_center_people": {
        "name": "Planning Center People",
        "description": "AI-callable wrapper for the Planning Center People API. List/search people, households, campuses, workflows, lists, and birthdays. Supports guarded create/update with dry-run.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_people",
        "tags": ["planning_center", "people", "church"],
    },
    "planning_center_calendar": {
        "name": "Planning Center Calendar",
        "description": "AI-callable wrapper for the Planning Center Calendar API. List/search events, event instances, resources, rooms, and tags. Supports guarded create/update with dry-run.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_calendar",
        "tags": ["planning_center", "calendar", "events"],
    },
    "planning_center_services": {
        "name": "Planning Center Services",
        "description": "AI-callable wrapper for the Planning Center Services API. List service types, plans, plan items, plan people, songs, and teams. Supports guarded write actions.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_services",
        "tags": ["planning_center", "services", "worship"],
    },
    "planning_center_publishing": {
        "name": "Planning Center Publishing",
        "description": "AI-callable wrapper for the Planning Center Publishing API. Manage episodes, series, and speakers. Supports guarded create/update with dry-run.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_publishing",
        "tags": ["planning_center", "publishing", "media"],
    },
    "planning_center_giving": {
        "name": "Planning Center Giving",
        "description": "AI-callable wrapper for the Planning Center Giving API. Read-only access to donations, funds, batches, designations, recurring donations, and refunds.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_giving",
        "tags": ["planning_center", "giving", "finance"],
    },
    "planning_center_groups": {
        "name": "Planning Center Groups",
        "description": "AI-callable wrapper for the Planning Center Groups API. List/search groups, memberships, group events, and group types. Supports guarded group event creation.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_groups",
        "tags": ["planning_center", "groups", "community"],
    },
    "planning_center_registrations": {
        "name": "Planning Center Registrations",
        "description": "AI-callable wrapper for the Planning Center Registrations API. Read-only access to registration events, attendees, categories, selections, and signup locations.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_registrations",
        "tags": ["planning_center", "registrations", "events"],
    },
    "planning_center_checkins": {
        "name": "Planning Center Check-Ins",
        "description": "AI-callable wrapper for the Planning Center Check-Ins API. Read-only access to check-in events, locations, attendees, and event periods.",
        "is_destructive": False,
        "mcp_tool_name": "planning_center_checkins",
        "tags": ["planning_center", "checkins", "children"],
    },
    "vimeo": {
        "name": "Vimeo",
        "description": "AI-callable wrapper for the Vimeo API. List/search videos, get video details, find livestreams, update metadata, and prepare upload tickets. Uses VIMEO_ACCESS_TOKEN for auth.",
        "is_destructive": False,
        "mcp_tool_name": "vimeo",
        "tags": ["vimeo", "video", "media"],
    },
    "emailoctopus": {
        "name": "EmailOctopus",
        "description": "AI-callable wrapper for the EmailOctopus API. Manage mailing lists, contacts, campaigns, and templates. Supports guarded contact/campaign creation with dry-run.",
        "is_destructive": False,
        "mcp_tool_name": "emailoctopus",
        "tags": ["emailoctopus", "email", "marketing"],
    },
    "bitfocus_companion": {
        "name": "Bitfocus Companion",
        "description": "AI-callable wrapper for Bitfocus Companion HTTP remote control. Press buttons, rotate encoders, set button styles, manage custom/module variables, and rescan surfaces.",
        "is_destructive": False,
        "mcp_tool_name": "bitfocus_companion",
        "tags": ["companion", "streaming", "broadcast"],
    },
    "sermonshots": {
        "name": "SermonShots",
        "description": "AI-callable wrapper for the SermonShots API. Manage videos, clips, transcripts, and AI-generated sermon content (summaries, blog posts, devotionals, discussion guides).",
        "is_destructive": False,
        "mcp_tool_name": "sermonshots",
        "tags": ["sermonshots", "sermon", "ai", "content"],
    },
    "wordpress": {
        "name": "WordPress",
        "description": "AI-callable wrapper for the WordPress REST API v2. List and manage posts, pages, media, categories, tags, and search. Uses Application Password auth.",
        "is_destructive": False,
        "mcp_tool_name": "wordpress",
        "tags": ["wordpress", "cms", "website", "content"],
    },
}


def extract_shared_code():
    """Read shared utils and extract source code for each function/class."""
    with open(SHARED_PATH) as f:
        source = f.read()

    tree = ast.parse(source)
    items = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            lines = source.splitlines()
            code = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            items[name] = code

    return items


def get_import_block_details(lines):
    """Find the 'from shared.wrapper_utils import ...' block.

    Returns (start_idx, end_idx) or (None, None).
    """
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from shared.wrapper_utils import"):
            start = i
            if stripped.endswith("("):
                for j in range(i, len(lines)):
                    if ")" in lines[j]:
                        return (start, j + 1)
                return (start, len(lines))
            else:
                return (start, i + 1)
    return (None, None)


def inline_wrapper_source(service_name):
    """Read a wrapper, inline shared code, return self-contained source."""
    wrapper_path = os.path.join(SERVICES_DIR, service_name, "wrapper.py")

    with open(wrapper_path) as f:
        source = f.read()

    lines = source.splitlines(True)
    import_start, import_end = get_import_block_details(lines)

    if import_start is None:
        # Already inlined? Return as-is
        return source

    shared_code = extract_shared_code()

    # Always include these
    all_to_include = {
        "Timer",
        "error_exit",
        "error_result",
        "success_result",
        "parse_input",
        "require_action",
        "require_fields",
        "run_wrapper",
    }

    if service_name in PLANNING_CENTER_SERVICES:
        all_to_include.add("build_planning_center_auth")
        all_to_include.add("planning_center_request")

    if service_name in SIMPLE_API_SERVICES:
        all_to_include.add("simple_api_request")

    # Check source for build_dry_run_response usage
    if "build_dry_run_response" in source:
        all_to_include.add("build_dry_run_response")

    # Build inline block
    inline_lines = [
        "# ── Inline shared utilities ──────────────────────────────────────────\n",
        "\n",
    ]

    order = [
        "Timer",
        "error_exit",
        "error_result",
        "success_result",
        "parse_input",
        "require_action",
        "require_fields",
        "build_dry_run_response",
        "build_planning_center_auth",
        "planning_center_request",
        "simple_api_request",
        "run_wrapper",
    ]

    for name in order:
        if name in all_to_include and name in shared_code:
            inline_lines.append(shared_code[name])
            inline_lines.append("\n\n")

    # Find where sys.path.insert is
    sys_path_line = None
    for i, line in enumerate(lines):
        if "sys.path.insert" in line:
            sys_path_line = i
            break

    if sys_path_line is not None:
        new_source = "".join(lines[:sys_path_line])
    else:
        new_source = ""

    new_source += "".join(inline_lines)

    # Code after the import block
    code_start = import_end
    while code_start < len(lines) and lines[code_start].strip() == "":
        code_start += 1

    new_source += "".join(lines[code_start:])

    return new_source


def read_schema(service_name):
    """Read the schema.json for a service."""
    path = os.path.join(SERVICES_DIR, service_name, "schema.json")
    with open(path) as f:
        return json.load(f)


class Command(BaseCommand):
    help = "Install AI wrapper scripts into ScriptDash database as self-contained scripts with MCP exposure"

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            type=str,
            default="blackhawk",
            help="Username to own the scripts (default: blackhawk)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually creating/updating scripts",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        owner_username = options.get("owner", "blackhawk")

        try:
            owner = User.objects.get(username=owner_username)
        except User.DoesNotExist:
            raise CommandError(f'User "{owner_username}" not found')

        from app.models import Tag

        services = sorted(
            d
            for d in os.listdir(SERVICES_DIR)
            if os.path.isdir(os.path.join(SERVICES_DIR, d))
            and d != "shared"
            and d != "__pycache__"
            and os.path.exists(os.path.join(SERVICES_DIR, d, "wrapper.py"))
        )

        self.stdout.write(f"Installing {len(services)} AI wrapper scripts as user '{owner_username}'...\n")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for service in services:
            config = SERVICE_CONFIGS.get(service)
            if not config:
                self.stdout.write(self.style.WARNING(f"  ⚠ {service}: no config found, skipping"))
                skipped_count += 1
                continue

            try:
                # Inline the shared utils
                code = inline_wrapper_source(service)

                # Read schema
                schema = read_schema(service)

                # Create or update the script
                script, was_created = Script.objects.update_or_create(
                    name=config["name"],
                    defaults={
                        "description": config["description"],
                        "code": code,
                        "language": "python",
                        "dependencies": "requests>=2.31.0",
                        "owner": owner,
                        "expose_to_mcp": True,
                        "mcp_tool_name": config["mcp_tool_name"],
                        "input_schema": schema,
                        "is_destructive": config["is_destructive"],
                        "is_public": False,
                    },
                )

                # Set tags
                for tag_name in config.get("tags", []):
                    tag, _ = Tag.objects.get_or_create(
                        name=tag_name,
                        defaults={
                            "color": "#3b82f6",
                            "created_by": owner,
                        },
                    )
                    script.tags.add(tag)

                if was_created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Created:  {config['name']}"))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  🔄 Updated: {config['name']}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ {service}: {e}"))

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Updated: {updated_count}")
        self.stdout.write(f"Skipped: {skipped_count}")
        self.stdout.write(f"Total:   {created_count + updated_count + skipped_count}")
        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n⚠ Dry-run complete — no changes were saved to the database.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ All wrappers installed successfully!"))
