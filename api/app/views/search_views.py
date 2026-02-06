"""
Search Views for Global Search API

Provides endpoints for:
- Global search across alerts, wallets, transactions
- Entity-specific search
- Search suggestions and autocomplete
"""

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
from urllib.parse import quote

from blockchain.models import Wallet as BlockchainWallet, Chain, SubChain
from blockchain.models_wallet_nicknames import WalletNickname

from ..models.alerts import AlertInstance
from ..models.alert_templates import AlertTemplate
from ..models.groups import GenericGroup, GroupType, SYSTEM_GROUP_ACCOUNTS


class GlobalSearchView(APIView):
    """
    GET: Search across all entities (alerts, wallets, transactions, pages)

    Query params:
    - q: Search query (required)
    - limit: Max results per type (default: 5)
    - types: Comma-separated list of types to search (optional)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 5))
        types_param = request.query_params.get('types', '')

        if not query:
            return Response({
                'query': query,
                'results': [],
                'total': 0
            })

        # Parse types filter
        allowed_types = ['page', 'action', 'alert', 'wallet', 'transaction', 'template']
        if types_param:
            types = [t.strip() for t in types_param.split(',') if t.strip() in allowed_types]
        else:
            types = allowed_types

        results = []
        user = request.user

        # Search Alerts
        if 'alert' in types:
            alerts = AlertInstance.objects.filter(
                Q(name__icontains=query) | Q(nl_description__icontains=query),
                user=user
            )[:limit]

            for alert in alerts:
                results.append({
                    'id': str(alert.id),
                    'type': 'alert',
                    'title': alert.name,
                    'subtitle': (alert.nl_description or '')[:100] if alert.nl_description else None,
                    'url': f'/dashboard/alerts/{alert.id}',
                'icon': 'bell',
                'metadata': {
                    'enabled': alert.enabled,
                    'chains': alert.get_chains() if hasattr(alert, 'get_chains') else [],
                }
            })

        # Search Alert Templates
        if 'template' in types:
            templates = AlertTemplate.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query),
                Q(is_public=True) | Q(created_by=user)
            )[:limit]

            for template in templates:
                results.append({
                    'id': str(template.id),
                    'type': 'template',
                    'title': template.name,
                    'subtitle': template.description[:100] if template.description else None,
                    'url': f'/dashboard/marketplace/{template.id}',
                    'icon': 'chart',
                    'metadata': {
                        'target_kind': template.target_kind,
                        # v2 templates compute usage dynamically (instances are pinned to versions).
                        'usage_count': template.instances.count(),
                    }
                })

        # Add static pages that match query
        if 'page' in types:
            pages = self._get_matching_pages(query, limit)
            results.extend(pages)

        # Add actions that match query
        if 'action' in types:
            actions = self._get_matching_actions(query, limit)
            results.extend(actions)

        return Response({
            'query': query,
            'results': results,
            'total': len(results)
        })

    def _get_matching_pages(self, query, limit):
        """Get static pages matching the query"""
        pages = [
            {'id': 'dashboard', 'title': 'Dashboard', 'subtitle': 'Main dashboard overview', 'url': '/dashboard', 'icon': 'home'},
            {'id': 'alerts', 'title': 'Alerts', 'subtitle': 'Manage your alerts', 'url': '/dashboard/alerts', 'icon': 'bell'},
            {'id': 'wallets', 'title': 'Wallets', 'subtitle': 'Manage your wallets', 'url': '/dashboard/wallets', 'icon': 'wallet'},
            {'id': 'marketplace', 'title': 'Marketplace', 'subtitle': 'Discover alert templates', 'url': '/dashboard/marketplace', 'icon': 'compass'},
            {'id': 'api', 'title': 'Developer API', 'subtitle': 'API documentation and keys', 'url': '/dashboard/api', 'icon': 'code'},
            {'id': 'profile', 'title': 'Profile', 'subtitle': 'Your profile settings', 'url': '/dashboard/profile', 'icon': 'user'},
            {'id': 'team', 'title': 'Team', 'subtitle': 'Team management', 'url': '/dashboard/team', 'icon': 'users'},
            {'id': 'settings', 'title': 'Settings', 'subtitle': 'Account settings', 'url': '/dashboard/settings', 'icon': 'settings'},
            {'id': 'security', 'title': 'Security', 'subtitle': 'Security settings', 'url': '/dashboard/settings/security', 'icon': 'shield'},
            {'id': 'billing', 'title': 'Billing', 'subtitle': 'Billing and subscription', 'url': '/dashboard/settings/billing', 'icon': 'credit-card'},
            {'id': 'help', 'title': 'Help & Support', 'subtitle': 'Get help and support', 'url': '/dashboard/help', 'icon': 'help-circle'},
        ]

        query_lower = query.lower()
        matching = [
            {**p, 'type': 'page'}
            for p in pages
            if query_lower in p['title'].lower() or query_lower in p['subtitle'].lower()
        ][:limit]

        return matching

    def _get_matching_actions(self, query, limit):
        """Get actions matching the query"""
        actions = [
            {'id': 'create-alert', 'title': 'Create New Alert', 'subtitle': 'Set up a new blockchain alert', 'icon': 'plus', 'metadata': {'action': 'create-alert'}},
            {'id': 'add-wallet', 'title': 'Add Wallet', 'subtitle': 'Connect a new wallet', 'icon': 'plus', 'metadata': {'action': 'add-wallet'}},
            {'id': 'export-data', 'title': 'Export Data', 'subtitle': 'Download your data', 'icon': 'download', 'metadata': {'action': 'export-data'}},
            {'id': 'logout', 'title': 'Logout', 'subtitle': 'Sign out of your account', 'icon': 'log-out', 'metadata': {'action': 'logout'}},
        ]

        query_lower = query.lower()
        matching = [
            {**a, 'type': 'action', 'url': None}
            for a in actions
            if query_lower in a['title'].lower() or query_lower in a['subtitle'].lower()
        ][:limit]

        return matching


class SearchAlertsView(APIView):
    """
    GET: Search alerts specifically

    Query params:
    - q: Search query
    - chain: Filter by chain
    - enabled: Filter by enabled status
    - limit: Max results (default: 20)
    - offset: Pagination offset
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        chain = request.query_params.get('chain')
        enabled = request.query_params.get('enabled')
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        user = request.user
        queryset = AlertInstance.objects.filter(user=user)

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )

        if chain:
            queryset = queryset.filter(chain_name=chain)

        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == 'true')

        total = queryset.count()
        alerts = queryset.order_by('-created_at')[offset:offset + limit]

        results = [{
            'id': str(alert.id),
            'type': 'alert',
            'title': alert.name,
            'subtitle': alert.description,
            'url': f'/dashboard/alerts/{alert.id}',
            'icon': 'bell',
            'metadata': {
                'enabled': alert.enabled,
                'chain': alert.chain_name,
                'created_at': alert.created_at.isoformat(),
            }
        } for alert in alerts]

        return Response({
            'query': query,
            'results': results,
            'total': total,
            'limit': limit,
            'offset': offset
        })


class SearchWalletsView(APIView):
    """
    GET: Search wallets

    Query params:
    - q: Search query (address or label)
    - chain: Filter by chain
    - limit: Max results (default: 20)
    - offset: Pagination offset
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        chain = request.query_params.get('chain')
        limit = min(int(request.query_params.get('limit', 20)), 100)
        offset = max(int(request.query_params.get('offset', 0)), 0)

        # Accounts label overrides (preferred display names)
        accounts_group = GenericGroup.objects.filter(
            owner=request.user,
            group_type=GroupType.WALLET,
            settings__system_key=SYSTEM_GROUP_ACCOUNTS,
        ).first()

        accounts_members = (accounts_group.member_data.get('members', {}) if accounts_group else {}) or {}
        accounts_member_keys = set(accounts_members.keys())
        accounts_labels = {
            key: (meta.get('label') or '')
            for key, meta in accounts_members.items()
            if isinstance(meta, dict)
        }

        nickname_rows = WalletNickname.objects.filter(user=request.user).values(
            "wallet_address",
            "chain_id",
            "custom_name",
        )
        nicknames_by_address_chain = {
            f"{row['wallet_address']}:{row['chain_id']}": row["custom_name"]
            for row in nickname_rows
        }

        queryset = BlockchainWallet.objects.select_related('blockchain')

        if chain:
            queryset = queryset.filter(blockchain__symbol__iexact=chain.strip())

        if query:
            if ':' in query:
                parts = [p.strip() for p in query.split(':') if p.strip()]
                if len(parts) >= 3:
                    network, subnet = parts[0], parts[1]
                    address = ':'.join(parts[2:])
                    queryset = queryset.filter(
                        blockchain__symbol__iexact=network,
                        subnet__iexact=subnet,
                        address__iexact=address,
                    )
                elif len(parts) == 2:
                    network, subnet = parts[0], parts[1]
                    queryset = queryset.filter(
                        blockchain__symbol__iexact=network,
                        subnet__iexact=subnet,
                    )
                else:
                    queryset = queryset.filter(
                        Q(address__icontains=query) |
                        Q(name__icontains=query) |
                        Q(derived_name__icontains=query)
                    )
            else:
                queryset = queryset.filter(
                    Q(address__icontains=query) |
                    Q(name__icontains=query) |
                    Q(derived_name__icontains=query)
                )

        total = queryset.count()
        wallets = queryset.order_by('-updated_at')[offset:offset + limit]

        # Map (network, subnet) -> chain_id for nickname resolution.
        networks = {(w.blockchain_id or "").upper() for w in wallets if w.blockchain_id}
        subnets = {(w.subnet or "").lower() for w in wallets if w.subnet}

        chain_by_network: dict[str, Chain] = {}
        if networks:
            chain_filter = Q()
            for network in sorted(networks):
                chain_filter |= Q(native_token__iexact=network)
            chains = Chain.objects.filter(chain_filter, enabled=True)
            chain_by_network = {str(c.native_token or "").upper(): c for c in chains if c.native_token}

        subnet_chain_id: dict[tuple[str, str], int] = {}
        if chain_by_network and subnets:
            subchain_filter = Q()
            for subnet in sorted(subnets):
                subchain_filter |= Q(name__iexact=subnet)

            subchains = SubChain.objects.filter(
                chain__in=list(chain_by_network.values()),
                enabled=True,
            ).filter(subchain_filter)

            for sc in subchains:
                network = str(getattr(sc.chain, "native_token", "") or "").upper()
                subnet = str(sc.name or "").lower()
                if not network or not subnet:
                    continue
                if sc.network_id is None:
                    continue
                subnet_chain_id[(network, subnet)] = int(sc.network_id)

        def _truncate_middle(value: str, prefix: int = 6, suffix: int = 4) -> str:
            if not value:
                return ''
            if len(value) <= prefix + suffix + 3:
                return value
            return f"{value[:prefix]}...{value[-suffix:]}"

        results = []
        for wallet in wallets:
            network = (wallet.blockchain_id or '').upper()
            subnet = (wallet.subnet or '').lower()
            address = wallet.address or ''
            wallet_key = f"{network}:{subnet}:{address}"

            in_accounts = wallet_key in accounts_member_keys
            accounts_label = accounts_labels.get(wallet_key, '').strip() or None

            chain_id: int | None = None
            chain = chain_by_network.get(network)
            if chain:
                chain_id = subnet_chain_id.get((network, subnet)) or getattr(chain, "chain_id", None)

            nickname = None
            if chain_id is not None:
                nickname = nicknames_by_address_chain.get(f"{address.lower()}:{int(chain_id)}")

            title = accounts_label or nickname or _truncate_middle(address)
            subtitle = wallet_key
            url = f"/dashboard/wallets/{quote(wallet_key, safe='')}" if in_accounts else '/dashboard/wallets'

            results.append({
                'id': str(wallet.id),
                'type': 'wallet',
                'title': title,
                'subtitle': subtitle,
                'url': url,
                'icon': 'wallet',
                'metadata': {
                    'wallet_key': wallet_key,
                    'address': address,
                    'network': network,
                    'subnet': subnet,
                    'label': accounts_label,
                    'nickname': nickname,
                    'in_accounts': in_accounts,
                }
            })

        return Response({
            'query': query,
            'results': results,
            'total': total,
            'limit': limit,
            'offset': offset,
        })


class SearchTransactionsView(APIView):
    """
    GET: Search transactions

    Query params:
    - q: Search query (hash, address)
    - chain: Filter by chain
    - limit: Max results (default: 20)
    - offset: Pagination offset
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        chain = request.query_params.get('chain')
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        # TODO: Implement transaction search when Transaction model is available
        # For now, return empty results
        return Response({
            'query': query,
            'results': [],
            'total': 0,
            'limit': limit,
            'offset': offset,
            'message': 'Transaction search not yet implemented'
        })


class SearchSuggestionsView(APIView):
    """
    GET: Get search suggestions for autocomplete

    Query params:
    - q: Partial query for suggestions
    - limit: Max suggestions (default: 10)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        limit = int(request.query_params.get('limit', 10))

        if len(query) < 2:
            return Response({
                'query': query,
                'suggestions': []
            })

        user = request.user
        suggestions = []

        # Get alert name suggestions
        alert_names = AlertInstance.objects.filter(
            user=user,
            name__icontains=query
        ).values_list('name', flat=True).distinct()[:limit]

        for name in alert_names:
            suggestions.append({
                'text': name,
                'type': 'alert',
                'icon': 'bell'
            })

        # Get template suggestions
        template_names = AlertTemplate.objects.filter(
            Q(is_public=True) | Q(created_by=user),
            name__icontains=query
        ).values_list('name', flat=True).distinct()[:limit]

        for name in template_names:
            suggestions.append({
                'text': name,
                'type': 'template',
                'icon': 'chart'
            })

        # Deduplicate and limit
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s['text'] not in seen:
                seen.add(s['text'])
                unique_suggestions.append(s)
            if len(unique_suggestions) >= limit:
                break

        return Response({
            'query': query,
            'suggestions': unique_suggestions
        })
