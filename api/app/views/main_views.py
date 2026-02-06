"""
Django REST Framework Views for Enhanced Alert API
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Max, Q, Exists, OuterRef
from django.shortcuts import get_object_or_404

from ..models.alerts import (
    AlertInstance, AlertChangeLog, AlertExecution, DefaultNetworkAlert
)
from ..serializers import (
    AlertInstanceSerializer, AlertInstanceCreateRequestSerializer, AlertInstanceListSerializer,
    AlertChangeLogSerializer, AlertExecutionSerializer,
    DefaultNetworkAlertSerializer,
    PreviewConfigSerializer, PreviewResultSerializer,
)
from ..services.nats_service import (
    publish_alert_created_sync, publish_alert_updated_sync,
    publish_alert_enabled_sync, publish_alert_disabled_sync,
)
from ..services.alert_runtime_projection import NOTIFICATION_OVERRIDE_KEY
from blockchain.models import Chain, SubChain


class AlertInstanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for AlertInstance CRUD operations (user subscriptions to alerts)
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['enabled', 'version', 'event_type', 'sub_event', 'template']
    search_fields = ['name', 'nl_description']
    ordering_fields = ['created_at', 'updated_at', 'name', 'version']
    ordering = ['-created_at', '-version']

    def get_queryset(self):
        """Get alert instances for the authenticated user"""
        queryset = AlertInstance.objects.filter(user=self.request.user)

        # Filter by chain if specified
        chain_name = self.request.query_params.get('chain')
        if chain_name:
            chain_raw = str(chain_name).strip().lower()
            chain_part, _, network_part = chain_raw.partition("-")
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

            filters = Q()
            if chain_id is not None:
                filters |= Q(_standalone_spec__trigger__chain_id=chain_id)

            if chain_part:
                # AlertTemplate v2 scope lives inside the versioned template_spec. The list endpoint
                # can only safely filter using instance-local fields (trigger_config + targets).
                filters |= Q(trigger_config__chains__contains=[chain_part])
                filters |= Q(trigger_config__chains__contains=[chain_raw])
                if network_part:
                    filters |= Q(trigger_config__chains__contains=[f"{chain_part}-{network_part}"])

            if filters:
                queryset = queryset.filter(filters)

        # Filter by event type
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by sub-event
        sub_event = self.request.query_params.get('sub_event')
        if sub_event:
            queryset = queryset.filter(sub_event=sub_event)

        # Show only latest versions by default
        latest_only = self.request.query_params.get('latest_only', 'true').lower() == 'true'
        if latest_only and self.action == 'list':
            # Get latest version of each alert
            latest_versions = queryset.values('id').annotate(
                latest_version=Max('version')
            )

            version_filters = Q()
            for item in latest_versions:
                version_filters |= Q(id=item['id'], version=item['latest_version'])

            queryset = queryset.filter(version_filters)

        return queryset.select_related("user", "template", "target_group")

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return AlertInstanceCreateRequestSerializer
        elif self.action == 'list':
            return AlertInstanceListSerializer
        else:
            return AlertInstanceSerializer

    def create(self, request, *args, **kwargs):
        """
        Create an AlertInstance from a saved template bundle.

        Parse is async; instance creation cannot consume ProposedSpec/job_id directly.
        """
        import logging

        logger = logging.getLogger(__name__)
        serializer = AlertInstanceCreateRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        resolved_variables = data["_resolved_variable_values"]
        notification_overrides = data.get("_notification_overrides") or {}
        target_group = data.get("_target_group")
        target_keys = data.get("_target_keys") or []
        alert_type = data.get("_alert_type") or "wallet"

        template = data.get("_template_obj")
        tmpl_ver = data.get("_template_version_obj")

        if template is None or tmpl_ver is None:
            return Response(
                {"error": "Invalid request: missing template reference"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance_name = str(data.get("name") or "").strip() or str(template.name).strip()
        nl_description = str(template.description or template.name or "").strip()

        event_type_map = {
            "wallet": "ACCOUNT_EVENT",
            "token": "ASSET_EVENT",
            "contract": "CONTRACT_INTERACTION",
            "network": "PROTOCOL_EVENT",
            "protocol": "DEFI_EVENT",
            "nft": "ASSET_EVENT",
        }

        template_params = dict(resolved_variables)
        if notification_overrides:
            template_params[NOTIFICATION_OVERRIDE_KEY] = notification_overrides

        alert = AlertInstance.objects.create(
            name=instance_name,
            nl_description=nl_description,
            template=template,
            template_version=int(getattr(tmpl_ver, "template_version", 1) or 1),
            template_params=template_params,
            event_type=event_type_map.get(str(alert_type), "ACCOUNT_EVENT"),
            sub_event="CUSTOM",
            sub_event_confidence=1.0,
            enabled=bool(data.get("enabled", True)),
            user=request.user,
            alert_type=alert_type,
            target_group=target_group,
            target_keys=target_keys,
            trigger_type=data.get("trigger_type"),
            trigger_config=data.get("trigger_config") or {},
            processing_status="skipped",
        )

        try:
            publish_alert_created_sync(alert)
        except Exception as e:
            logger.error(f"Failed to publish alert created message: {e}")

        response_serializer = AlertInstanceSerializer(alert, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        """Update alert and publish to NATS"""
        alert = serializer.save()

        # Publish to NATS for cache sync
        try:
            publish_alert_updated_sync(alert)
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to publish alert updated message: {e}")

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get all versions of an alert instance"""
        alert_instance = self.get_object()
        versions = AlertInstance.objects.filter(id=alert_instance.id).order_by('-version')

        page = self.paginate_queryset(versions)
        if page is not None:
            serializer = AlertInstanceListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AlertInstanceListSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def version(self, request, pk=None):
        """Get a specific version of an alert instance"""
        alert_id = pk
        version = request.query_params.get('version')

        if not version:
            return Response(
                {'error': 'Version parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            alert_instance = AlertInstance.objects.get(
                id=alert_id,
                version=int(version),
                user=request.user
            )
        except (AlertInstance.DoesNotExist, ValueError):
            return Response(
                {'error': 'Alert instance version not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AlertInstanceSerializer(alert_instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def changelog(self, request, pk=None):
        """Get change log for an alert instance"""
        alert_instance = self.get_object()
        change_logs = AlertChangeLog.objects.filter(
            alert_instance__id=alert_instance.id
        ).order_by('-created_at')

        page = self.paginate_queryset(change_logs)
        if page is not None:
            serializer = AlertChangeLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AlertChangeLogSerializer(change_logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def executions(self, request, pk=None):
        """Get execution history for an alert instance"""
        alert_instance = self.get_object()
        executions = AlertExecution.objects.filter(
            alert_instance__id=alert_instance.id
        ).order_by('-started_at')

        page = self.paginate_queryset(executions)
        if page is not None:
            serializer = AlertExecutionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AlertExecutionSerializer(executions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """Enable an alert instance"""
        alert_instance = self.get_object()

        if alert_instance.enabled:
            return Response(
                {'message': 'Alert instance is already enabled'},
                status=status.HTTP_200_OK
            )

        # Create change log
        AlertChangeLog.objects.create(
            alert_instance=alert_instance,
            from_version=alert_instance.version,
            to_version=alert_instance.version,
            change_type='enabled',
            changed_fields=['enabled'],
            old_values={'enabled': False},
            new_values={'enabled': True},
            changed_by=request.user
        )

        alert_instance.enabled = True
        alert_instance.save(update_fields=['enabled'])

        # Publish to NATS for re-activation
        try:
            publish_alert_enabled_sync(alert_instance)
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to publish alert enabled message: {e}")

        return Response({'message': 'Alert instance enabled successfully'})

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """Disable an alert instance"""
        alert_instance = self.get_object()

        if not alert_instance.enabled:
            return Response(
                {'message': 'Alert instance is already disabled'},
                status=status.HTTP_200_OK
            )

        # Create change log
        AlertChangeLog.objects.create(
            alert_instance=alert_instance,
            from_version=alert_instance.version,
            to_version=alert_instance.version,
            change_type='disabled',
            changed_fields=['enabled'],
            old_values={'enabled': True},
            new_values={'enabled': False},
            changed_by=request.user
        )

        alert_instance.enabled = False
        alert_instance.save(update_fields=['enabled'])

        # Publish to NATS for deactivation
        try:
            publish_alert_disabled_sync(alert_instance)
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to publish alert disabled message: {e}")

        return Response({'message': 'Alert instance disabled successfully'})

    @action(detail=False, methods=['post'])
    def parse(self, request):
        """Parse natural language description asynchronously.

        PRD: /docs/prd/apps/api/PRD-NLP-Service-USDT.md

        Returns 202 Accepted with job_id for tracking progress via WebSocket events.

        WebSocket Events (NATS subject: ws.events):
            - nlp.status
            - nlp.complete
            - nlp.error
        """
        import logging
        import math
        import uuid
        from datetime import timedelta
        logger = logging.getLogger(__name__)

        from django.conf import settings
        from django.core.cache import cache
        from django.utils import timezone
        from app.services.nlp import is_nlp_configured
        from app.services.nlp.pipelines import DEFAULT_PIPELINE_ID

        nl_description = request.data.get('nl_description', '')
        client_request_id = request.data.get('client_request_id')
        context = request.data.get('context') or {}
        pipeline_id = request.data.get("pipeline_id") or DEFAULT_PIPELINE_ID
        pipeline_id = str(pipeline_id).strip() or DEFAULT_PIPELINE_ID

        if not nl_description or not nl_description.strip():
            return Response(
                {'error': 'nl_description is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not is_nlp_configured():
            return Response(
                {'error': 'NLP service not configured. Check GEMINI_API_KEY setting.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Rate limit (default: 10 requests/min/user; Redis-backed cache)
        user_id = str(request.user.id)
        rate_limit = int(getattr(settings, "NLP_PARSE_RATE_LIMIT_PER_MIN", 10))
        window_secs = 60
        bucket = int(math.floor(timezone.now().timestamp() / window_secs))
        rate_key = f"nlp:parse_rate:{user_id}:{bucket}"

        current_count = cache.get(rate_key, 0)
        if current_count >= rate_limit:
            return Response(
                {"error": "Rate limit exceeded. Try again soon."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if current_count == 0:
            cache.set(rate_key, 1, timeout=window_secs + 5)
        else:
            try:
                cache.incr(rate_key)
            except Exception:
                cache.set(rate_key, current_count + 1, timeout=window_secs + 5)

        job_id = str(uuid.uuid4())

        # Async mode: enqueue Django Task
        try:
            from app.tasks.nlp_tasks import parse_nl_description

            max_chars = int(getattr(settings, "NLP_NL_DESCRIPTION_MAX_CHARS", 500))
            sanitized = str(nl_description).strip()
            if len(sanitized) > max_chars:
                sanitized = sanitized[:max_chars]

            parse_nl_description.enqueue(
                user_id=user_id,
                nl_description=sanitized,
                job_id=job_id,
                client_request_id=str(client_request_id).strip() if client_request_id else None,
                context=context if isinstance(context, dict) else {},
                pipeline_id=pipeline_id,
            )

            logger.info(f"NLP parse job queued: job_id={job_id}, user_id={user_id}")

            ttl_secs = int(getattr(settings, "NLP_PROPOSED_SPEC_TTL_SECS", 3600))
            expires_at = timezone.now() + timedelta(seconds=ttl_secs)

            return Response(
                {
                    'success': True,
                    'job_id': job_id,
                    'status': 'queued',
                    'expires_at': expires_at.isoformat(),
                    'estimated_wait_ms': int(getattr(settings, "NLP_ESTIMATED_WAIT_MS", 2000)),
                },
                status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            logger.error(f"Failed to enqueue NLP task: {e}")
            return Response(
                {'error': f'Failed to queue NLP task: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='parse/(?P<job_id>[^/.]+)')
    def parse_result(self, request, job_id=None):
        """Get result of async NLP parse job.

        Fallback endpoint for clients without WebSocket support.
        Returns cached ProposedSpec if job completed, or status if still processing.

        Response (completed):
            {
                "status": "completed",
                "spec": {...}
            }

        Response (pending/processing):
            {
                "status": "processing",
                "message": "Job is still processing"
            }

        Response (not found):
            {
                "status": "not_found",
                "error": "Job not found or expired (TTL: 1 hour)"
            }
        """
        from django.core.cache import cache

        if not job_id:
            return Response(
                {'error': 'job_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cache key scoped by user_id - only owner can access their job results
        user_id = str(request.user.id)
        cache_key = f"nlp:proposed_spec:{user_id}:{job_id}"
        proposed_spec = cache.get(cache_key)

        if proposed_spec:
            return Response({
                'status': 'completed',
                'result': proposed_spec,
                'job_id': job_id,
            })

        # Check if job is still in queue/processing
        # For now, just return not found (could check task queue in future)
        return Response({
            'status': 'not_found',
            'error': 'Job not found or expired (TTL: 1 hour)',
            'job_id': job_id,
        }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='inline-preview')
    def inline_preview(self, request):
        """Preview/dry-run an alert using inline spec (no template_id required).

        Accepts the parsed NLP result spec directly, enabling preview before
        the alert is created. This is the primary flow for NL-based alert creation.

        Request:
            {
                "spec": {
                    "condition": {
                        "expression": "value_usd > 1000",
                        "config": {...}
                    },
                    "trigger": {"chain_id": "ethereum"},
                    "scope": {"addresses": ["0x..."]}
                },
                "alert_type": "wallet",
                "time_range": "7d",
                "limit": 100,
                "include_near_misses": true
            }

        Response:
            {
                "success": true,
                "summary": {...},
                "sample_triggers": [...],
                "evaluation_mode": "per_row"
            }
        """
        import asyncio
        import logging
        import uuid

        from ..services.preview import (
            PreviewDataFetcher, SimpleDjangoEvaluator
        )

        logger = logging.getLogger(__name__)

        # Extract spec from request
        spec = request.data.get('spec')
        if not spec:
            return Response(
                {'error': 'spec is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate preview config
        config_serializer = PreviewConfigSerializer(data=request.data)
        config_serializer.is_valid(raise_exception=True)
        config = config_serializer.validated_data

        time_range = config.get('time_range', '7d')
        limit = config.get('limit', 1000)
        include_near_misses = config.get('include_near_misses', False)
        addresses = config.get('addresses', [])
        chain = config.get('chain', '')
        alert_type = request.data.get('alert_type', 'wallet')

        try:
            # Extract condition expression from spec
            condition = spec.get('condition', {})
            expression = condition.get('expression', '')

            if not expression:
                # Try config.raw format
                config_raw = condition.get('config', {})
                expression = config_raw.get('raw', '')

            if not expression:
                # Try alternate condition formats
                conditions = spec.get('conditions', {})
                if conditions:
                    all_conditions = conditions.get('all', [])
                    any_conditions = conditions.get('any', [])
                    if all_conditions:
                        expression = ' and '.join(
                            self._condition_to_expression(c) for c in all_conditions
                        )
                    elif any_conditions:
                        expression = ' or '.join(
                            self._condition_to_expression(c) for c in any_conditions
                        )

            if not expression:
                return Response(
                    {'error': 'No condition expression found in spec'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get chain from spec or override
            if not chain:
                trigger = spec.get('trigger', {})
                chain = trigger.get('chain_id', 'ethereum')
                if isinstance(chain, int):
                    chain_map = {1: 'ethereum', 137: 'polygon', 42161: 'arbitrum'}
                    chain = chain_map.get(chain, 'ethereum')

            # Get addresses from spec or override
            if not addresses:
                try:
                    addresses = alert_instance.get_addresses()
                except Exception:
                    addresses = []

            # Analyze expression
            evaluator = SimpleDjangoEvaluator()
            can_evaluate, reason = evaluator.can_evaluate(expression)

            if not can_evaluate:
                return Response({
                    'success': False,
                    'summary': {
                        'total_events_evaluated': 0,
                        'would_have_triggered': 0,
                        'trigger_rate': 0.0,
                        'estimated_daily_triggers': 0.0,
                        'evaluation_time_ms': 0.0,
                    },
                    'sample_triggers': [],
                    'near_misses': [],
                    'evaluation_mode': 'aggregate',
                    'expression': expression,
                    'requires_wasmcloud': True,
                    'wasmcloud_reason': reason,
                    'error': f'Complex expression requires wasmCloud evaluation: {reason}',
                })

            # Fetch historical data
            fetcher = PreviewDataFetcher()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                data_result = loop.run_until_complete(
                    fetcher.fetch_for_alert_type(
                        alert_type=alert_type,
                        chain=chain,
                        addresses=addresses,
                        time_range=time_range,
                        limit=limit,
                    )
                )
            finally:
                loop.close()

            if data_result.error:
                return Response({
                    'success': False,
                    'error': f'Failed to fetch historical data: {data_result.error}',
                    'summary': {
                        'total_events_evaluated': 0,
                        'would_have_triggered': 0,
                        'trigger_rate': 0.0,
                        'estimated_daily_triggers': 0.0,
                        'evaluation_time_ms': data_result.query_time_ms,
                    },
                    'sample_triggers': [],
                    'near_misses': [],
                    'evaluation_mode': 'per_row',
                    'requires_wasmcloud': False,
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Evaluate
            eval_result = evaluator.evaluate(
                expression=expression,
                data=data_result.rows,
                include_near_misses=include_near_misses,
            )

            # Calculate statistics
            total_evaluated = eval_result.total_evaluated
            match_count = eval_result.match_count
            trigger_rate = match_count / total_evaluated if total_evaluated > 0 else 0.0

            time_range_days = {'1h': 1/24, '24h': 1, '7d': 7, '30d': 30}
            days = time_range_days.get(time_range, 7)
            estimated_daily = match_count / days if days > 0 else 0.0

            # Build sample triggers
            sample_triggers = []
            for row in eval_result.matched_rows[:10]:
                timestamp = row.get('block_timestamp') or row.get('timestamp')
                sample_triggers.append({
                    'timestamp': timestamp,
                    'data': row,
                    'matched_condition': expression,
                })

            # Build near-miss results
            near_misses = []
            for nm in eval_result.near_misses[:10]:
                near_miss_info = nm.get('_near_miss_info', {})
                timestamp = nm.get('block_timestamp') or nm.get('timestamp')
                near_misses.append({
                    'timestamp': timestamp,
                    'data': {k: v for k, v in nm.items() if k != '_near_miss_info'},
                    'threshold_distance': near_miss_info.get('distance_percent', 0),
                    'explanation': (
                        f"{near_miss_info.get('field')} was {near_miss_info.get('value')} "
                        f"({near_miss_info.get('distance_percent', 0):.2f}% from threshold "
                        f"{near_miss_info.get('threshold')})"
                    ) if near_miss_info else '',
                })

            response_data = {
                'success': True,
                'preview_id': str(uuid.uuid4()),
                'summary': {
                    'total_events_evaluated': total_evaluated,
                    'would_have_triggered': match_count,
                    'trigger_rate': round(trigger_rate, 4),
                    'estimated_daily_triggers': round(estimated_daily, 2),
                    'evaluation_time_ms': round(
                        data_result.query_time_ms + eval_result.evaluation_time_ms, 2
                    ),
                },
                'sample_triggers': sample_triggers,
                'near_misses': near_misses,
                'evaluation_mode': eval_result.mode.value,
                'expression': expression,
                'data_source': data_result.data_source,
                'time_range': time_range,
                'requires_wasmcloud': False,
            }

            logger.info(
                f"Inline preview completed for user {request.user.id}: "
                f"{match_count}/{total_evaluated} matches"
            )

            return Response(response_data)

        except Exception as e:
            logger.error(f"Inline preview failed for user {request.user.id}: {e}")
            return Response(
                {'error': f'Preview failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Preview/dry-run an existing alert instance against historical data.

        Tests the alert's condition against historical blockchain data to show
        how often it would have triggered. Useful for debugging and tuning alerts.

        Request:
            {
                "time_range": "24h",
                "limit": 100,
                "include_near_misses": true,
                "explain_mode": true
            }

        Response:
            {
                "success": true,
                "summary": {
                    "total_events_evaluated": 500,
                    "would_have_triggered": 5,
                    "trigger_rate": 0.01,
                    "estimated_daily_triggers": 5.0,
                    "evaluation_time_ms": 32.1
                },
                "sample_triggers": [...],
                "near_misses": [...],
                "evaluation_mode": "per_row",
                "requires_wasmcloud": false
            }
        """
        import asyncio
        import logging
        import uuid

        from ..services.preview import (
            PreviewDataFetcher, SimpleDjangoEvaluator
        )

        logger = logging.getLogger(__name__)
        alert_instance = self.get_object()

        # Validate request
        config_serializer = PreviewConfigSerializer(data=request.data)
        config_serializer.is_valid(raise_exception=True)
        config = config_serializer.validated_data

        time_range = config.get('time_range', '7d')
        limit = config.get('limit', 1000)
        include_near_misses = config.get('include_near_misses', False)
        addresses = config.get('addresses', [])
        chain = config.get('chain', '')

        try:
            # Get the rendered spec from the alert instance
            spec = alert_instance.spec
            if not spec:
                return Response(
                    {'error': 'Alert instance has no spec. Processing may have failed.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract condition expression
            condition = spec.get('condition', {})
            expression = condition.get('expression', '')

            if not expression:
                # Try alternate condition formats
                conditions = spec.get('conditions', {})
                if conditions:
                    all_conditions = conditions.get('all', [])
                    any_conditions = conditions.get('any', [])
                    if all_conditions:
                        expression = ' and '.join(
                            self._condition_to_expression(c) for c in all_conditions
                        )
                    elif any_conditions:
                        expression = ' or '.join(
                            self._condition_to_expression(c) for c in any_conditions
                        )

            if not expression:
                return Response(
                    {'error': 'No condition expression found in alert spec'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get chain from spec or override
            if not chain:
                trigger = spec.get('trigger', {})
                chain = trigger.get('chain_id', 'ethereum')
                if isinstance(chain, int):
                    chain_map = {1: 'ethereum', 137: 'polygon', 42161: 'arbitrum'}
                    chain = chain_map.get(chain, 'ethereum')

            # Get addresses from spec or override
            if not addresses:
                scope = spec.get('scope', {})
                addresses = scope.get('addresses', [])
                if not addresses:
                    targets = scope.get('targets', [])
                    if isinstance(targets, list):
                        addresses = [t for t in targets if isinstance(t, str)]

            # Analyze expression
            evaluator = SimpleDjangoEvaluator()
            can_evaluate, reason = evaluator.can_evaluate(expression)

            if not can_evaluate:
                return Response({
                    'success': False,
                    'summary': {
                        'total_events_evaluated': 0,
                        'would_have_triggered': 0,
                        'trigger_rate': 0.0,
                        'estimated_daily_triggers': 0.0,
                        'evaluation_time_ms': 0.0,
                    },
                    'sample_triggers': [],
                    'near_misses': [],
                    'evaluation_mode': 'aggregate',
                    'expression': expression,
                    'requires_wasmcloud': True,
                    'wasmcloud_reason': reason,
                    'error': f'Complex expression requires wasmCloud evaluation: {reason}',
                })

            # Fetch historical data
            fetcher = PreviewDataFetcher()
            alert_type = alert_instance.alert_type or 'wallet'

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                data_result = loop.run_until_complete(
                    fetcher.fetch_for_alert_type(
                        alert_type=alert_type,
                        chain=chain,
                        addresses=addresses,
                        time_range=time_range,
                        limit=limit,
                    )
                )
            finally:
                loop.close()

            if data_result.error:
                return Response({
                    'success': False,
                    'error': f'Failed to fetch historical data: {data_result.error}',
                    'summary': {
                        'total_events_evaluated': 0,
                        'would_have_triggered': 0,
                        'trigger_rate': 0.0,
                        'estimated_daily_triggers': 0.0,
                        'evaluation_time_ms': data_result.query_time_ms,
                    },
                    'sample_triggers': [],
                    'near_misses': [],
                    'evaluation_mode': 'per_row',
                    'requires_wasmcloud': False,
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Evaluate
            eval_result = evaluator.evaluate(
                expression=expression,
                data=data_result.rows,
                include_near_misses=include_near_misses,
            )

            # Calculate statistics
            total_evaluated = eval_result.total_evaluated
            match_count = eval_result.match_count
            trigger_rate = match_count / total_evaluated if total_evaluated > 0 else 0.0

            time_range_days = {'1h': 1/24, '24h': 1, '7d': 7, '30d': 30}
            days = time_range_days.get(time_range, 7)
            estimated_daily = match_count / days if days > 0 else 0.0

            # Build sample triggers
            sample_triggers = []
            for row in eval_result.matched_rows[:10]:
                timestamp = row.get('block_timestamp') or row.get('timestamp')
                sample_triggers.append({
                    'timestamp': timestamp,
                    'data': row,
                    'matched_condition': expression,
                })

            # Build near-miss results
            near_misses = []
            for nm in eval_result.near_misses[:10]:
                near_miss_info = nm.get('_near_miss_info', {})
                timestamp = nm.get('block_timestamp') or nm.get('timestamp')
                near_misses.append({
                    'timestamp': timestamp,
                    'data': {k: v for k, v in nm.items() if k != '_near_miss_info'},
                    'threshold_distance': near_miss_info.get('distance_percent', 0),
                    'explanation': (
                        f"{near_miss_info.get('field')} was {near_miss_info.get('value')} "
                        f"({near_miss_info.get('distance_percent', 0):.2f}% from threshold "
                        f"{near_miss_info.get('threshold')})"
                    ) if near_miss_info else '',
                })

            response_data = {
                'success': True,
                'preview_id': str(uuid.uuid4()),
                'summary': {
                    'total_events_evaluated': total_evaluated,
                    'would_have_triggered': match_count,
                    'trigger_rate': round(trigger_rate, 4),
                    'estimated_daily_triggers': round(estimated_daily, 2),
                    'evaluation_time_ms': round(
                        data_result.query_time_ms + eval_result.evaluation_time_ms, 2
                    ),
                },
                'sample_triggers': sample_triggers,
                'near_misses': near_misses,
                'evaluation_mode': eval_result.mode.value,
                'expression': expression,
                'data_source': data_result.data_source,
                'time_range': time_range,
                'requires_wasmcloud': False,
            }

            logger.info(
                f"Preview completed for alert instance {alert_instance.id}: "
                f"{match_count}/{total_evaluated} matches"
            )

            return Response(response_data)

        except Exception as e:
            logger.error(f"Preview failed for alert instance {alert_instance.id}: {e}")
            return Response(
                {'error': f'Preview failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _condition_to_expression(self, condition: dict) -> str:
        """Convert a condition dict to a simple expression string."""
        left = condition.get('left', {})
        right = condition.get('right', {})
        operator = condition.get('operator', '==')

        if isinstance(left, dict):
            field = left.get('path', '') or left.get('value', '')
            if field.startswith('$.tx.'):
                field = field.replace('$.tx.', '')
            elif field.startswith('$.datasources.'):
                parts = field.split('.')
                if len(parts) >= 3:
                    field = parts[-1]
        else:
            field = str(left)

        if isinstance(right, dict):
            value = right.get('value', '')
        else:
            value = right

        return f"{field} {operator} {value}"


class DefaultNetworkAlertViewSet(viewsets.ModelViewSet):
    """Read-only + toggle API for system default network alerts."""

    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = DefaultNetworkAlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DefaultNetworkAlert.objects.select_related(
            "chain",
            "alert_template",
        ).order_by("chain__display_name", "subnet")


class ChainViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Chain information
    """
    
    queryset = Chain.objects.filter(enabled=True).order_by('display_name')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'display_name']
    ordering_fields = ['display_name', 'created_at']
    ordering = ['display_name']
    
    def get_serializer_class(self):
        """Return appropriate serializer"""
        # Simple serializer for chains
        from rest_framework import serializers
        
        class ChainSerializer(serializers.ModelSerializer):
            class Meta:
                model = Chain
                fields = ['id', 'name', 'display_name', 'chain_id', 'native_token']
        
        return ChainSerializer
    
    @action(detail=True, methods=['get'])
    def sub_chains(self, request, pk=None):
        """Get sub-chains for a specific chain"""
        chain = self.get_object()
        sub_chains = SubChain.objects.filter(
            chain=chain, 
            enabled=True
        ).order_by('display_name')
        
        # Simple serializer for sub-chains
        from rest_framework import serializers
        
        class SubChainSerializer(serializers.ModelSerializer):
            class Meta:
                model = SubChain
                fields = ['id', 'name', 'display_name', 'network_id', 'is_testnet']
        
        serializer = SubChainSerializer(sub_chains, many=True)
        return Response(serializer.data)


# ===================================================================
# Notification Endpoint ViewSets
# ===================================================================

from ..models.notifications import (
    NotificationChannelEndpoint,
    TeamMemberNotificationOverride,
    NotificationChannelVerification,
)
from ..serializers import (
    NotificationChannelEndpointSerializer,
    TeamNotificationChannelEndpointSerializer,
    NotificationChannelVerificationSerializer,
    TeamMemberNotificationOverrideSerializer,
)
from organizations.models import Team, TeamMember, TeamMemberRole
import random
from datetime import timedelta
from django.utils import timezone


class NotificationChannelEndpointViewSet(viewsets.ModelViewSet):
    """ViewSet for user notification channel endpoints"""

    serializer_class = NotificationChannelEndpointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's endpoints"""
        return NotificationChannelEndpoint.objects.filter(
            owner_type='user',
            owner_id=self.request.user.id
        ).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def request_verification(self, request, pk=None):
        """Request a verification code for this endpoint"""
        endpoint = self.get_object()

        # Only create verification for endpoints that require it
        if not endpoint.requires_reverification:
            return Response(
                {'error': 'This channel type does not require verification'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate 6-digit code
        verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        # Create verification record
        verification = NotificationChannelVerification.objects.create(
            endpoint=endpoint,
            verification_code=verification_code,
            verification_type='initial' if not endpoint.verified else 're_enable',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        # TODO: Send verification code via appropriate channel
        # For now, just return the verification ID

        return Response({
            'verification_id': str(verification.id),
            'expires_at': verification.expires_at.isoformat(),
            'message': f'Verification code sent to {endpoint.channel_type}'
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify an endpoint with a verification code"""
        endpoint = self.get_object()
        verification_code = request.data.get('verification_code')

        if not verification_code:
            return Response(
                {'error': 'verification_code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find valid verification
        try:
            verification = NotificationChannelVerification.objects.get(
                endpoint=endpoint,
                verification_code=verification_code,
                verified_at__isnull=True
            )
        except NotificationChannelVerification.DoesNotExist:
            return Response(
                {'error': 'Invalid verification code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if expired
        if verification.is_expired():
            return Response(
                {'error': 'Verification code has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark as verified
        verification.verified_at = timezone.now()
        verification.save()

        endpoint.verified = True
        endpoint.verified_at = timezone.now()
        endpoint.save()

        return Response({
            'message': 'Endpoint verified successfully',
            'endpoint': self.get_serializer(endpoint).data
        })


class TeamNotificationChannelEndpointViewSet(viewsets.ModelViewSet):
    """ViewSet for team notification channel endpoints"""

    serializer_class = TeamNotificationChannelEndpointSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return team endpoints for teams the user is a member of"""
        user_teams = TeamMember.objects.filter(user=self.request.user).values_list('team_id', flat=True)
        return NotificationChannelEndpoint.objects.filter(
            owner_type='team',
            owner_id__in=user_teams
        ).order_by('-created_at')

    def check_team_permissions(self, team_id, required_roles):
        """Check if user has required role in team"""
        try:
            member = TeamMember.objects.get(team_id=team_id, user=self.request.user)
            return member.role in required_roles
        except TeamMember.DoesNotExist:
            return False

    def create(self, request, *args, **kwargs):
        """Create team endpoint - requires owner or admin role"""
        team_id = request.data.get('owner_id')

        if not team_id:
            return Response(
                {'error': 'owner_id (team ID) is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check permissions
        if not self.check_team_permissions(team_id, [TeamMemberRole.OWNER, TeamMemberRole.ADMIN]):
            return Response(
                {'error': 'Only team owners and admins can create team endpoints'},
                status=status.HTTP_403_FORBIDDEN
            )

        response = super().create(request, *args, **kwargs)

        # Explicitly add owner_id to response data
        # Note: DRF's serializer may not include owner_id in response even though
        # it's in the fields list and saved to the database
        if 'owner_id' not in response.data:
            response.data['owner_id'] = str(team_id)

        return response

    def perform_create(self, serializer):
        """Create endpoint and set owner to team."""
        # owner_id comes from validated_data (user provides it in request)
        # owner_type is always 'team' for this ViewSet
        team_id = serializer.validated_data['owner_id']

        serializer.save(
            owner_type='team',
            owner_id=team_id,  # Explicitly set owner_id from validated data
            created_by=self.request.user
        )

    def update(self, request, *args, **kwargs):
        """Update team endpoint - requires owner or admin role"""
        endpoint = self.get_object()

        if not self.check_team_permissions(endpoint.owner_id, [TeamMemberRole.OWNER, TeamMemberRole.ADMIN]):
            return Response(
                {'error': 'Only team owners and admins can update team endpoints'},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete team endpoint - requires owner or admin role"""
        endpoint = self.get_object()

        if not self.check_team_permissions(endpoint.owner_id, [TeamMemberRole.OWNER, TeamMemberRole.ADMIN]):
            return Response(
                {'error': 'Only team owners and admins can delete team endpoints'},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().destroy(request, *args, **kwargs)


class TeamMemberNotificationOverrideViewSet(viewsets.ModelViewSet):
    """ViewSet for team member notification overrides"""

    serializer_class = TeamMemberNotificationOverrideSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only the current user's overrides"""
        return TeamMemberNotificationOverride.objects.filter(
            member=self.request.user
        ).select_related('team')

    def list(self, request, *args, **kwargs):
        """List all user's overrides across all teams"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Get or create override for specific team (pk is team_id)"""
        try:
            team = Team.objects.get(id=pk)
        except Team.DoesNotExist:
            return Response(
                {'error': 'Team not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is member of team
        if not TeamMember.objects.filter(team=team, user=request.user).exists():
            return Response(
                {'error': 'You are not a member of this team'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get or create override
        override, created = TeamMemberNotificationOverride.objects.get_or_create(
            team=team,
            member=request.user
        )

        serializer = self.get_serializer(override)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """Update override for specific team (pk is team_id)"""
        pk = kwargs.get('pk')

        try:
            team = Team.objects.get(id=pk)
        except Team.DoesNotExist:
            return Response(
                {'error': 'Team not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            override = TeamMemberNotificationOverride.objects.get(
                team=team,
                member=request.user
            )
        except TeamMemberNotificationOverride.DoesNotExist:
            return Response(
                {'error': 'Override not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Use partial from kwargs (True for PATCH, False for PUT)
        partial = kwargs.get('partial', False)
        serializer = self.get_serializer(override, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def disable_all_team_notifications(self, request):
        """Disable all team notifications for a specific team"""
        team_id = request.data.get('team')

        if not team_id:
            return Response(
                {'error': 'team ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response(
                {'error': 'Team not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get or create override
        override, created = TeamMemberNotificationOverride.objects.get_or_create(
            team=team,
            member=request.user
        )

        override.team_notifications_enabled = False
        override.save()

        return Response({
            'message': 'All team notifications disabled',
            'override': self.get_serializer(override).data
        })

    @action(detail=False, methods=['post'])
    def enable_all_team_notifications(self, request):
        """Enable all team notifications for a specific team"""
        team_id = request.data.get('team')

        if not team_id:
            return Response(
                {'error': 'team ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response(
                {'error': 'Team not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get or create override
        override, created = TeamMemberNotificationOverride.objects.get_or_create(
            team=team,
            member=request.user
        )

        override.team_notifications_enabled = True
        override.save()

        return Response({
            'message': 'All team notifications enabled',
            'override': self.get_serializer(override).data
        })
