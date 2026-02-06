from django.conf import settings
from django.db import migrations, models
import uuid


def seed_billing_plans(apps, schema_editor):
    BillingPlan = apps.get_model("app", "BillingPlan")

    if BillingPlan.objects.exists():
        return

    BillingPlan.objects.bulk_create([
        BillingPlan(
            id=uuid.uuid4(),
            name="Free",
            slug="free",
            price_usd=0,
            billing_cycle="monthly",
            features=[
                "3 Wallets",
                "100 Alerts/month",
                "Basic notifications",
                "Community support",
            ],
            not_included=[
                "API access",
                "Custom webhooks",
                "Priority support",
            ],
            max_wallets=3,
            max_alerts=100,
            max_api_calls=0,
            max_notifications=1000,
            is_active=True,
            is_default=True,
        ),
        BillingPlan(
            id=uuid.uuid4(),
            name="Pro",
            slug="pro",
            price_usd=49,
            billing_cycle="monthly",
            features=[
                "50 Wallets",
                "1,000 Alerts/month",
                "All notification channels",
                "100K API calls/month",
                "Email support",
                "Custom webhooks",
            ],
            not_included=[
                "Dedicated support",
            ],
            max_wallets=50,
            max_alerts=1000,
            max_api_calls=100000,
            max_notifications=5000,
            is_active=True,
            is_default=False,
        ),
        BillingPlan(
            id=uuid.uuid4(),
            name="Enterprise",
            slug="enterprise",
            price_usd=199,
            billing_cycle="monthly",
            features=[
                "Unlimited Wallets",
                "Unlimited Alerts",
                "All notification channels",
                "Unlimited API calls",
                "Dedicated support",
                "Custom integrations",
                "SLA guarantee",
                "On-premise option",
            ],
            not_included=[],
            max_wallets=0,
            max_alerts=0,
            max_api_calls=0,
            max_notifications=0,
            is_active=True,
            is_default=False,
        ),
    ])


def seed_api_endpoints(apps, schema_editor):
    ApiEndpoint = apps.get_model("app", "ApiEndpoint")

    if ApiEndpoint.objects.exists():
        return

    ApiEndpoint.objects.bulk_create([
        ApiEndpoint(
            id=uuid.uuid4(),
            path="/api/v1/wallets",
            method="GET",
            description="List all wallets",
            parameters=[
                {"name": "page", "type": "integer", "required": False, "description": "Page number"},
                {"name": "limit", "type": "integer", "required": False, "description": "Items per page"},
            ],
        ),
        ApiEndpoint(
            id=uuid.uuid4(),
            path="/api/v1/alerts",
            method="GET",
            description="List all alerts",
            parameters=[
                {"name": "status", "type": "string", "required": False, "description": "Filter by status"},
            ],
        ),
        ApiEndpoint(
            id=uuid.uuid4(),
            path="/api/v1/alerts",
            method="POST",
            description="Create a new alert",
            example_request={
                "name": "Large Transfer Alert",
                "description": "Monitor for transfers above 100 ETH",
                "conditions": {"amount": {"gt": "100000000000000000000"}},
            },
        ),
    ])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0019_add_nlp_pipelines"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingPlan",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("price_usd", models.DecimalField(decimal_places=2, max_digits=10)),
                ("billing_cycle", models.CharField(choices=[("monthly", "Monthly"), ("yearly", "Yearly")], max_length=20)),
                ("features", models.JSONField(default=list)),
                ("not_included", models.JSONField(default=list)),
                ("max_wallets", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("max_alerts", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("max_api_calls", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("max_notifications", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("is_active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "billing_plans",
                "verbose_name": "Billing Plan",
                "verbose_name_plural": "Billing Plans",
            },
        ),
        migrations.CreateModel(
            name="BillingSubscription",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("status", models.CharField(choices=[("active", "Active"), ("trialing", "Trialing"), ("canceled", "Canceled"), ("past_due", "Past Due")], default="active", max_length=20)),
                ("current_period_start", models.DateTimeField()),
                ("current_period_end", models.DateTimeField()),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="subscriptions", to="app.billingplan")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="billing_subscriptions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "billing_subscriptions",
                "verbose_name": "Billing Subscription",
                "verbose_name_plural": "Billing Subscriptions",
            },
        ),
        migrations.CreateModel(
            name="BillingInvoice",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("amount_usd", models.DecimalField(decimal_places=2, max_digits=10)),
                ("status", models.CharField(choices=[("paid", "Paid"), ("open", "Open"), ("void", "Void"), ("uncollectible", "Uncollectible")], default="open", max_length=20)),
                ("billed_at", models.DateTimeField()),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subscription", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="invoices", to="app.billingsubscription")),
            ],
            options={
                "db_table": "billing_invoices",
                "verbose_name": "Billing Invoice",
                "verbose_name_plural": "Billing Invoices",
            },
        ),
        migrations.CreateModel(
            name="ApiKey",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("key_prefix", models.CharField(max_length=32, unique=True)),
                ("key_hash", models.CharField(max_length=64)),
                ("access_level", models.CharField(choices=[("full", "Full"), ("read_only", "Read Only"), ("limited", "Limited")], default="full", max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("expires_soon", "Expires Soon"), ("expired", "Expired"), ("revoked", "Revoked")], default="active", max_length=20)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                ("rate_limit_per_minute", models.PositiveIntegerField(default=60)),
                ("rate_limit_per_day", models.PositiveIntegerField(default=10000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="api_keys", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "developer_api_keys",
                "verbose_name": "API Key",
                "verbose_name_plural": "API Keys",
            },
        ),
        migrations.CreateModel(
            name="ApiUsageRecord",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("date", models.DateField()),
                ("requests", models.PositiveIntegerField(default=0)),
                ("errors", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("api_key", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="usage_records", to="app.apikey")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="api_usage_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "developer_api_usage",
                "verbose_name": "API Usage Record",
                "verbose_name_plural": "API Usage Records",
                "unique_together": {("user", "date", "api_key")},
            },
        ),
        migrations.CreateModel(
            name="ApiEndpoint",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("path", models.CharField(max_length=255)),
                ("method", models.CharField(choices=[("GET", "GET"), ("POST", "POST"), ("PUT", "PUT"), ("PATCH", "PATCH"), ("DELETE", "DELETE")], max_length=10)),
                ("description", models.TextField()),
                ("parameters", models.JSONField(blank=True, default=list)),
                ("example_request", models.JSONField(blank=True, null=True)),
                ("example_response", models.JSONField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "developer_api_endpoints",
                "verbose_name": "API Endpoint",
                "verbose_name_plural": "API Endpoints",
                "unique_together": {("path", "method")},
            },
        ),
        migrations.AddIndex(
            model_name="billingplan",
            index=models.Index(fields=["slug"], name="billing_pl_slug_1b8b0c_idx"),
        ),
        migrations.AddIndex(
            model_name="billingplan",
            index=models.Index(fields=["is_active"], name="billing_pl_is_acti_0300ff_idx"),
        ),
        migrations.AddIndex(
            model_name="billingsubscription",
            index=models.Index(fields=["user"], name="billing_su_user_id_4fdef4_idx"),
        ),
        migrations.AddIndex(
            model_name="billingsubscription",
            index=models.Index(fields=["status"], name="billing_su_status_56bcd9_idx"),
        ),
        migrations.AddIndex(
            model_name="billinginvoice",
            index=models.Index(fields=["status"], name="billing_in_status_1e42e2_idx"),
        ),
        migrations.AddIndex(
            model_name="billinginvoice",
            index=models.Index(fields=["billed_at"], name="billing_in_billed_3f1f41_idx"),
        ),
        migrations.AddIndex(
            model_name="apikey",
            index=models.Index(fields=["user"], name="developer_a_user_id_5b0b75_idx"),
        ),
        migrations.AddIndex(
            model_name="apikey",
            index=models.Index(fields=["status"], name="developer_a_status_4bb3c5_idx"),
        ),
        migrations.AddIndex(
            model_name="apiusagerecord",
            index=models.Index(fields=["user", "date"], name="developer_a_user_id_96b6a7_idx"),
        ),
        migrations.AddIndex(
            model_name="apiendpoint",
            index=models.Index(fields=["path"], name="developer_a_path_9b6b6f_idx"),
        ),
        migrations.AddIndex(
            model_name="apiendpoint",
            index=models.Index(fields=["is_active"], name="developer_a_is_acti_2e4a30_idx"),
        ),
        migrations.RunPython(seed_billing_plans, migrations.RunPython.noop),
        migrations.RunPython(seed_api_endpoints, migrations.RunPython.noop),
    ]
