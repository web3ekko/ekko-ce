from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from app.services.nlp.eval.seed_prompts import seed_prompt_cases_as_dicts


class Command(BaseCommand):
    help = "Write the initial NLP seed prompt set (no user data) to a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="test-results/nlp_seed_prompts.json",
            help="Output path (default: test-results/nlp_seed_prompts.json)",
        )

    def handle(self, *args, **options):
        out = Path(str(options["out"])).expanduser()
        if not out.parent.exists():
            raise CommandError(f"Parent directory does not exist: {out.parent}")

        data = seed_prompt_cases_as_dicts()
        out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(data)} seed prompts to {out}"))

