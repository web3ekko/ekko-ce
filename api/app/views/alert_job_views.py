"""
Alert Job Configuration API Views

API endpoints for actors (blockchain transaction processors) and Alert Scheduler Provider
to query active alerts and record job creation.

These endpoints are used by:
- wasmCloud actors: Query event-driven alerts to process blockchain transactions
- Alert Scheduler Provider: Query periodic/one-time alerts to create scheduled jobs
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from app.models import AlertInstance
from app.serializers.alert_job_serializers import (
    AlertJobConfigSerializer,
    RecordJobCreationSerializer,
)


class GetActiveAlertsByTriggerTypeView(APIView):
    """
    Query active alerts by trigger type.

    Used by Alert Scheduler Provider to fetch periodic and one_time alerts.
    NO AUTHENTICATION REQUIRED - External service endpoint.
    """
    permission_classes = []

    def get(self, request):
        """
        Query Parameters:
            trigger_type (str): One of 'periodic', 'one_time', or 'event_driven'

        Returns:
            200 OK: {
                "count": 5,
                "alerts": [...]
            }
            400 Bad Request: Missing or invalid trigger_type parameter
        """
        trigger_type = request.GET.get('trigger_type')

        if not trigger_type:
            return Response(
                {'error': 'trigger_type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_trigger_types = ['periodic', 'one_time', 'event_driven']
        if trigger_type not in valid_trigger_types:
            return Response(
                {
                    'error': f'Invalid trigger_type. Must be one of: {", ".join(valid_trigger_types)}'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Query active alerts of the specified trigger type
        # Get only the latest version of each alert
        alerts = AlertInstance.objects.filter(
            enabled=True,
            trigger_type=trigger_type
        ).select_related('template').order_by('name', '-version')

        # Filter to latest version only
        latest_alerts = []
        seen_templates = set()

        for alert in alerts:
            key = (alert.template_id, alert.name) if alert.template else alert.name
            if key not in seen_templates:
                seen_templates.add(key)
                latest_alerts.append(alert)

        serializer = AlertJobConfigSerializer(latest_alerts, many=True)

        return Response({
            'count': len(latest_alerts),
            'alerts': serializer.data
        })


class GetMatchingEventDrivenAlertsView(APIView):
    """
    Query event-driven alerts matching blockchain transaction criteria.

    Used by wasmCloud actors processing blockchain transactions to find
    alerts that should be evaluated for the current transaction.
    NO AUTHENTICATION REQUIRED - External service endpoint.
    """
    permission_classes = []

    def get(self, request):
        """
        Query Parameters:
            chain (str): Required. Blockchain network
            event_type (str): Optional. Event type to filter
            address (str): Optional. Wallet address to filter

        Returns:
            200 OK: {
                "count": 3,
                "alerts": [...],
                "filters": {...}
            }
            400 Bad Request: Missing chain parameter
        """
        chain = request.GET.get('chain')
        event_type = request.GET.get('event_type')
        address = request.GET.get('address')

        if not chain:
            return Response(
                {'error': 'chain parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Start with event_driven alerts only
        alerts = AlertInstance.objects.filter(
            enabled=True,
            trigger_type='event_driven'
        )

        # Filter by chain.
        #
        # Legacy v1 behavior used AlertTemplate v1 columns (template.spec/template.scope_*).
        # AlertTemplate v2 lives in a separate model and does not expose these fields directly,
        # so we rely on instance-local fields (standalone spec + trigger_config + target_keys).
        chain_raw = str(chain).strip().lower()
        chain_part, _, network_part = chain_raw.partition("-")
        network = network_part or "mainnet"

        chain_id_map = {
            "ethereum": 1,
            "eth": 1,
            "polygon": 137,
            "matic": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "avax": 43114,
            "base": 8453,
            "bsc": 56,
            "binance": 56,
            "bnb": 56,
        }
        chain_id = chain_id_map.get(chain_part)

        # SQLite JSONField backend does not support `__contains` lookups. Use a
        # python-side filter in tests/dev when running on SQLite.
        supports_json_contains = bool(getattr(connection.features, "supports_json_field_contains", False))
        if supports_json_contains:
            filters = Q()
            if chain_id is not None:
                filters |= Q(_standalone_spec__trigger__chain_id=chain_id)

            # Back-compat: allow trigger_config chains list to satisfy the filter.
            if chain_part:
                filters |= Q(trigger_config__chains__contains=[chain_part])
                filters |= Q(trigger_config__chains__contains=[chain_raw])
                filters |= Q(trigger_config__chains__contains=[f"{chain_part}-{network}"])
            else:
                filters |= Q(trigger_config__chains__contains=[chain_raw])

            alerts = alerts.filter(filters)

            # Filter by event_type if provided
            if event_type:
                alerts = alerts.filter(Q(trigger_config__event_types__contains=[event_type]))

            # Filter by address if provided
            if address:
                from app.models.groups import normalize_network_subnet_address_key

                prefix_map = {
                    "ethereum": "ETH",
                    "eth": "ETH",
                    "polygon": "MATIC",
                    "matic": "MATIC",
                    "arbitrum": "ARB",
                    "optimism": "OP",
                    "avalanche": "AVAX",
                    "avax": "AVAX",
                    "base": "BASE",
                    "bsc": "BNB",
                    "binance": "BNB",
                    "bnb": "BNB",
                }
                chain_prefix = prefix_map.get(chain_part, chain_part.upper() if chain_part else "ETH")
                target_key = normalize_network_subnet_address_key(f"{chain_prefix}:{network}:{address}")

                alerts = alerts.filter(
                    Q(target_keys__contains=[target_key])
                    | Q(trigger_config__addresses__contains=[address])
                    | Q(template_params__address=address)
                    | Q(template_params__wallet=address)
                )
        else:
            from app.models.groups import normalize_network_subnet_address_key

            chain_candidates = []
            if chain_part:
                chain_candidates = [chain_part, chain_raw, f"{chain_part}-{network}"]
            else:
                chain_candidates = [chain_raw]
            chain_candidates_set = {c for c in chain_candidates if isinstance(c, str) and c.strip()}

            target_key = None
            if address:
                prefix_map = {
                    "ethereum": "ETH",
                    "eth": "ETH",
                    "polygon": "MATIC",
                    "matic": "MATIC",
                    "arbitrum": "ARB",
                    "optimism": "OP",
                    "avalanche": "AVAX",
                    "avax": "AVAX",
                    "base": "BASE",
                    "bsc": "BNB",
                    "binance": "BNB",
                    "bnb": "BNB",
                }
                chain_prefix = prefix_map.get(chain_part, chain_part.upper() if chain_part else "ETH")
                target_key = normalize_network_subnet_address_key(f"{chain_prefix}:{network}:{address}")

            def _matches_chain(alert: AlertInstance) -> bool:
                spec = alert._standalone_spec or {}
                trigger = spec.get("trigger") if isinstance(spec, dict) else {}
                spec_chain_id = trigger.get("chain_id") if isinstance(trigger, dict) else None
                if chain_id is not None and spec_chain_id == chain_id:
                    return True
                trig = alert.trigger_config or {}
                chains = trig.get("chains") if isinstance(trig, dict) else None
                if not isinstance(chains, list):
                    return False
                normalized = {str(c).strip().lower() for c in chains if isinstance(c, str) and c.strip()}
                return any(str(c).strip().lower() in normalized for c in chain_candidates_set)

            def _matches_event_type(alert: AlertInstance) -> bool:
                if not event_type:
                    return True
                trig = alert.trigger_config or {}
                types = trig.get("event_types") if isinstance(trig, dict) else None
                if not isinstance(types, list):
                    return False
                normalized = {str(t).strip().lower() for t in types if isinstance(t, str) and t.strip()}
                return str(event_type).strip().lower() in normalized

            def _matches_address(alert: AlertInstance) -> bool:
                if not address:
                    return True
                addr = str(address).strip().lower()
                trig = alert.trigger_config or {}
                if isinstance(trig, dict):
                    addrs = trig.get("addresses")
                    if isinstance(addrs, list) and any(str(a).strip().lower() == addr for a in addrs):
                        return True
                if target_key and isinstance(getattr(alert, "target_keys", None), list):
                    if target_key in alert.target_keys:
                        return True
                params = alert.template_params or {}
                if isinstance(params, dict):
                    for k in ("address", "wallet"):
                        v = params.get(k)
                        if isinstance(v, str) and v.strip().lower() == addr:
                            return True
                return False

            filtered = [a for a in list(alerts) if _matches_chain(a) and _matches_event_type(a) and _matches_address(a)]
            filtered.sort(key=lambda a: (str(a.name or ""), -(int(getattr(a, "version", 0) or 0))))
            alerts = filtered

        # Get latest versions only
        latest_alerts = []
        seen_templates = set()

        for alert in alerts.order_by('name', '-version') if hasattr(alerts, "order_by") else alerts:
            key = (alert.template_id, alert.name) if alert.template else alert.name
            if key not in seen_templates:
                seen_templates.add(key)
                latest_alerts.append(alert)

        serializer = AlertJobConfigSerializer(latest_alerts, many=True)

        return Response({
            'count': len(latest_alerts),
            'alerts': serializer.data,
            'filters': {
                'chain': chain,
                **({"event_type": event_type} if event_type else {}),
                **({"address": address} if address else {}),
            }
        })


class RecordJobCreationView(APIView):
    """
    Record that an AlertJob was created for an alert.

    Used by actors and Alert Scheduler Provider to track when jobs are created.
    NO AUTHENTICATION REQUIRED - External service endpoint.
    """
    permission_classes = []

    def post(self, request):
        """
        Request Body:
            {
                "alert_id": "uuid",
                "created_at": "2025-11-15T22:30:00Z"
            }

        Returns:
            200 OK: {
                "success": true,
                "job_creation_count": 11,
                "last_job_created_at": "2025-11-15T22:30:00Z"
            }
            400 Bad Request: Invalid alert_id or created_at
        """
        serializer = RecordJobCreationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        alert_id = serializer.validated_data['alert_id']
        created_at = serializer.validated_data['created_at']

        # Get the alert and update job creation tracking
        try:
            alert = AlertInstance.objects.get(id=alert_id)
        except AlertInstance.DoesNotExist:
            return Response(
                {'error': f'Alert with ID {alert_id} does not exist'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Increment count and update timestamp
        alert.job_creation_count += 1
        alert.last_job_created_at = created_at
        alert.save(update_fields=['job_creation_count', 'last_job_created_at'])

        return Response({
            'success': True,
            'job_creation_count': alert.job_creation_count,
            'last_job_created_at': alert.last_job_created_at.isoformat() if alert.last_job_created_at else None,
        })
