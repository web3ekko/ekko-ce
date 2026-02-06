"""
Management command to warm the Redis alert runtime cache.

Usage:
    python manage.py warm_alert_cache

This command projects AlertTemplates, AlertInstances, and runtime DatasourceCatalog
entries into Redis for the wasmCloud alert runtime (scheduler/processor/router).
"""

from django.core.management.base import BaseCommand
import json
import logging

import redis
from django.conf import settings

from app.models.alerts import AlertInstance
from app.models.alert_templates import AlertTemplateVersion
from app.services.alert_runtime_projection import AlertRuntimeProjection
from app.services.datasource_catalog.catalog import list_runtime_catalog_entries

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Warm Redis alert runtime cache"

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Include disabled alerts (default: only enabled)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing cache before warming',
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting alert runtime cache warming...")

        r = redis.from_url(settings.CACHES["default"]["LOCATION"], decode_responses=True)
        projector = AlertRuntimeProjection()

        if options["clear"]:
            self.stdout.write("Clearing existing alert runtime keys...")
            patterns = [
                "alerts:instance:*",
                "alerts:template:*",
                "alerts:executable:*",
                "alerts:event_idx:*",
                "alerts:targets:group_partitions:*",
                "alerts:targets:group:*",
                "datasource_catalog:*",
            ]
            deleted = 0
            for pattern in patterns:
                for key in r.scan_iter(match=pattern):
                    deleted += int(bool(r.delete(key)))
            r.delete("alerts:schedule:periodic")
            r.delete("alerts:schedule:one_time")
            self.stdout.write(self.style.SUCCESS(f"Cleared {deleted} keys"))

        # DatasourceCatalog (runtime, includes SQL)
        catalog_entries = list_runtime_catalog_entries()
        for entry in catalog_entries:
            r.set(
                f"datasource_catalog:{entry['catalog_id']}",
                json.dumps(entry, separators=(",", ":"), sort_keys=True),
            )
        self.stdout.write(self.style.SUCCESS(f"Projected {len(catalog_entries)} datasource catalog entries"))

        # Template bundles (versioned keys: alerts:template:{template_id}:{template_version}, alerts:executable:{template_id}:{template_version})
        bundle_count = 0
        for tmpl_ver in AlertTemplateVersion.objects.select_related("template").all():
            projected = projector.project_template_bundle(
                template_id=str(tmpl_ver.template_id), template_version=int(tmpl_ver.template_version)
            )
            if projected is not None:
                bundle_count += 1
        self.stdout.write(self.style.SUCCESS(f"Projected {bundle_count} template bundles"))

        # Instances (key: alerts:instance:{instance_id})
        instance_qs = AlertInstance.objects.select_related("template")
        if not options["all"]:
            instance_qs = instance_qs.filter(enabled=True)

        projected_instances = 0
        for instance in instance_qs:
            projector.project_instance(instance)
            projected_instances += 1

        self.stdout.write(self.style.SUCCESS("Cache warming complete:"))
        self.stdout.write(f"  Template bundles: {bundle_count}")
        self.stdout.write(f"  Instances: {projected_instances}")
