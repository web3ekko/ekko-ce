"""
Dashboard Views for Dashboard Stats API

Provides endpoints for:
- Quick dashboard statistics
- Recent activity feed
- Chain-specific statistics
"""

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from ..models.alerts import AlertInstance, AlertExecution
from ..models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS, GroupSubscription


class DashboardStatsView(APIView):
    """
    GET: Get quick dashboard statistics for the authenticated user

    Returns counts for alerts, wallets, groups, and recent activity summary
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        # Alert stats
        total_alerts = AlertInstance.objects.filter(user=user).count()
        active_alerts = AlertInstance.objects.filter(user=user, enabled=True).count()

        # Execution stats (last 24h and 7d)
        executions_24h = AlertExecution.objects.filter(
            alert_instance__user=user,
            created_at__gte=last_24h
        ).count()

        executions_7d = AlertExecution.objects.filter(
            alert_instance__user=user,
            created_at__gte=last_7d
        ).count()

        # Triggered alerts in last 24h
        triggered_24h = AlertExecution.objects.filter(
            alert_instance__user=user,
            created_at__gte=last_24h,
            result=True
        ).count()

        accounts_group = GenericGroup.objects.filter(
            owner=user,
            group_type=GroupType.WALLET,
            settings__system_key=SYSTEM_GROUP_ACCOUNTS,
        ).first()
        total_wallets = accounts_group.member_count if accounts_group else 0

        created_groups = GenericGroup.objects.filter(
            owner=user,
            group_type=GroupType.ALERT,
        ).count()
        subscribed_groups = GroupSubscription.objects.filter(owner=user, is_active=True).count()
        total_groups = GenericGroup.objects.filter(
            owner=user,
            group_type=GroupType.ALERT,
        ).count()

        return Response({
            'alerts': {
                'total': total_alerts,
                'active': active_alerts,
                'inactive': total_alerts - active_alerts,
            },
            'groups': {
                'created': created_groups,
                'subscribed': subscribed_groups,
                'total': total_groups,
            },
            'activity': {
                'executions_24h': executions_24h,
                'executions_7d': executions_7d,
                'triggered_24h': triggered_24h,
            },
            'wallets': {
                'total': total_wallets,
                'watched': total_wallets,
            },
            'timestamp': now.isoformat(),
        })


class DashboardActivityView(APIView):
    """
    GET: Get recent activity feed for the authenticated user

    Query params:
    - limit: Max items (default: 20, max: 100)
    - offset: Pagination offset
    - type: Filter by activity type (execution, alert_created, group_joined)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        limit = min(int(request.query_params.get('limit', 20)), 100)
        offset = int(request.query_params.get('offset', 0))
        activity_type = request.query_params.get('type')

        activities = []

        # Get recent alert executions
        if not activity_type or activity_type == 'execution':
            executions = AlertExecution.objects.filter(
                alert_instance__user=user
            ).select_related('alert_instance').order_by('-created_at')[:limit]

            for execution in executions:
                alert = execution.alert_instance
                # Get chains from spec - chains are stored in the JSON spec, not as a field
                chains = alert.get_chains() if hasattr(alert, 'get_chains') else []
                # Handle both string chains and dict chains (NLP-generated alerts use dicts)
                if chains:
                    chain_names = []
                    for chain in chains:
                        if isinstance(chain, dict):
                            chain_names.append(chain.get('chain_id') or chain.get('network') or 'Unknown')
                        else:
                            chain_names.append(str(chain))
                    chain_display = ', '.join(chain_names)
                else:
                    chain_display = alert.alert_type or 'Unknown'

                activities.append({
                    'id': str(execution.id),
                    'type': 'execution',
                    'title': f'Alert "{alert.name}" executed',
                    'subtitle': 'Triggered' if execution.result else 'Checked',
                    'timestamp': execution.created_at.isoformat(),
                    'metadata': {
                        'alert_id': str(alert.id),
                        'alert_name': alert.name,
                        'triggered': execution.result or False,
                        'chain': chain_display,
                        'alert_type': alert.alert_type,
                    }
                })

        # Get recently created alerts
        if not activity_type or activity_type == 'alert_created':
            recent_alerts = AlertInstance.objects.filter(
                user=user
            ).order_by('-created_at')[:limit]

            for alert in recent_alerts:
                # Get chains from spec - chains are stored in the JSON spec, not as a field
                chains = alert.get_chains() if hasattr(alert, 'get_chains') else []
                # Handle both string chains and dict chains (NLP-generated alerts use dicts)
                if chains:
                    chain_names = []
                    for chain in chains:
                        if isinstance(chain, dict):
                            chain_names.append(chain.get('chain_id') or chain.get('network') or 'Unknown')
                        else:
                            chain_names.append(str(chain))
                    chain_display = ', '.join(chain_names)
                else:
                    chain_display = alert.alert_type or 'Unknown'

                activities.append({
                    'id': f'alert-created-{alert.id}',
                    'type': 'alert_created',
                    'title': f'Created alert "{alert.name}"',
                    'subtitle': f'Monitoring {chain_display}',
                    'timestamp': alert.created_at.isoformat(),
                    'metadata': {
                        'alert_id': str(alert.id),
                        'alert_name': alert.name,
                        'chain': chain_display,
                        'alert_type': alert.alert_type,
                    }
                })

        # Sort all activities by timestamp (descending)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)

        # Apply pagination
        paginated = activities[offset:offset + limit]

        return Response({
            'activities': paginated,
            'total': len(activities),
            'limit': limit,
            'offset': offset,
        })


class DashboardChainStatsView(APIView):
    """
    GET: Get statistics broken down by blockchain/alert_type

    Query params:
    - chains: Comma-separated list of chains to include (optional)

    Note: Since chains are stored in the JSON spec rather than as a database field,
    we aggregate by alert_type and extract chains from specs for display.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        chains_param = request.query_params.get('chains', '')

        # Get chain filter
        chain_filter = None
        if chains_param:
            chain_filter = [c.strip().lower() for c in chains_param.split(',') if c.strip()]

        # Get all alerts for user
        alerts = AlertInstance.objects.filter(user=user)

        # Build chain stats by extracting chains from specs
        chain_stats = {}
        for alert in alerts:
            # Get chains from the alert spec
            chains = alert.get_chains() if hasattr(alert, 'get_chains') else []
            if not chains:
                chains = [alert.alert_type or 'unknown']

            for chain in chains:
                # Handle both string chains and dict chains (NLP-generated alerts use dicts)
                if isinstance(chain, dict):
                    chain_name = chain.get('chain_id') or chain.get('network') or 'unknown'
                else:
                    chain_name = str(chain)
                chain_lower = chain_name.lower()
                # Apply chain filter if specified
                if chain_filter and chain_lower not in chain_filter:
                    continue

                if chain_lower not in chain_stats:
                    chain_stats[chain_lower] = {
                        'chain': chain_name,
                        'total': 0,
                        'active': 0,
                    }
                chain_stats[chain_lower]['total'] += 1
                if alert.enabled:
                    chain_stats[chain_lower]['active'] += 1

        # Build response
        chains = []
        for chain_key, stat in sorted(chain_stats.items(), key=lambda x: -x[1]['total']):
            chains.append({
                'chain': stat['chain'],
                'alerts': {
                    'total': stat['total'],
                    'active': stat['active'],
                    'inactive': stat['total'] - stat['active'],
                },
                'icon': self._get_chain_icon(stat['chain']),
            })

        # Calculate totals
        total_alerts = sum(c['alerts']['total'] for c in chains)
        total_active = sum(c['alerts']['active'] for c in chains)

        return Response({
            'chains': chains,
            'summary': {
                'total_chains': len(chains),
                'total_alerts': total_alerts,
                'total_active': total_active,
            },
            'timestamp': timezone.now().isoformat(),
        })

    def _get_chain_icon(self, chain_name):
        """Map chain names to icon identifiers"""
        chain_icons = {
            'ethereum': 'eth',
            'ethereum-mainnet': 'eth',
            'bitcoin': 'btc',
            'bitcoin-mainnet': 'btc',
            'solana': 'sol',
            'solana-mainnet': 'sol',
            'polygon': 'polygon',
            'polygon-mainnet': 'polygon',
            'arbitrum': 'arbitrum',
            'arbitrum-mainnet': 'arbitrum',
            'optimism': 'optimism',
            'optimism-mainnet': 'optimism',
            'base': 'base',
            'base-mainnet': 'base',
            'avalanche': 'avax',
            'avalanche-mainnet': 'avax',
            'bnb': 'bnb',
            'bnb-mainnet': 'bnb',
        }
        return chain_icons.get(chain_name.lower(), 'generic')


class DashboardNetworkStatusView(APIView):
    """
    GET: Get real-time network status from provider status tracking.

    Returns status of blockchain data ingest providers reading from Redis
    where wasmCloud providers write their status via provider-status-common.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from ..services.provider_status import ProviderStatusService

        service = ProviderStatusService()
        provider_statuses = service.get_all_provider_statuses()

        # Transform provider data to network status format
        networks = []
        for provider in provider_statuses:
            for chain_id, sub in provider.get('subscriptions', {}).items():
                networks.append(self._transform_subscription(
                    provider, chain_id, sub
                ))

        # Return empty list if no providers registered (not mock data)
        return Response({
            'networks': networks,
            'providers': len(provider_statuses),
            'timestamp': timezone.now().isoformat()
        })

    def _transform_subscription(self, provider: dict, chain_id: str, sub: dict) -> dict:
        """Transform subscription status to network status format."""
        state = sub.get('state', 'unknown')
        last_block = sub.get('last_block')
        metrics = sub.get('metrics', {})

        # Map subscription state to status
        status_map = {
            'active': 'operational',
            'connecting': 'connecting',
            'reconnecting': 'degraded',
            'error': 'error',
            'stopped': 'offline'
        }

        return {
            'id': chain_id,
            'name': sub.get('chain_name', chain_id),
            'status': status_map.get(state, 'unknown'),
            'provider_id': provider.get('provider_id'),
            'provider_type': provider.get('provider_type'),
            'block_height': last_block.get('number') if last_block else None,
            'last_block_time': last_block.get('received_at') if last_block else None,
            'avg_latency_ms': metrics.get('avg_latency_ms'),
            'blocks_received': metrics.get('blocks_received', 0),
            'connection_errors': metrics.get('connection_errors', 0),
            'health_score': self._calculate_health_score(sub),
        }

    def _calculate_health_score(self, sub: dict) -> int:
        """Calculate health score 0-100 based on subscription metrics."""
        state = sub.get('state', 'unknown')
        if state == 'active':
            base = 100
        elif state == 'reconnecting':
            base = 70
        elif state == 'connecting':
            base = 50
        else:
            base = 0

        # Reduce score based on errors
        metrics = sub.get('metrics', {})
        errors = metrics.get('connection_errors', 0) + metrics.get('processing_errors', 0)
        penalty = min(errors * 2, 30)  # Max 30 point penalty

        return max(0, base - penalty)
