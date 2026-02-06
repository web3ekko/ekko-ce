"""
Django REST Framework ViewSets for GenericGroup and GroupSubscription models.

Provides API endpoints for:
- GenericGroup CRUD operations
- Member add/remove operations
- Group filtering by type
- GroupSubscription management
"""

import csv
import io
import json
from typing import List, Tuple

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404

from ..models.groups import (
    GenericGroup,
    GroupSubscription,
    GroupType,
    SYSTEM_GROUP_ACCOUNTS,
    UserWalletGroup,
    normalize_network_subnet_address_key,
)
from ..services.group_service import AlertValidationService
from ..serializers.group_serializers import (
    GenericGroupSerializer,
    GenericGroupListSerializer,
    GenericGroupCreateSerializer,
    GroupMemberSerializer,
    GroupMemberBulkSerializer,
    GroupMemberBulkUpdateSerializer,
    AccountsWalletAddSerializer,
    AccountsWalletBulkAddSerializer,
    GroupSubscriptionSerializer,
    GroupSubscriptionListSerializer,
    UserWalletGroupSerializer,
    UserWalletGroupCreateSerializer,
    UserWalletGroupUpdateSerializer,
    UserWalletGroupWalletKeysSerializer,
    UserWalletGroupImportSerializer,
)


class GenericGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for GenericGroup CRUD operations.

    Endpoints:
    - GET    /api/groups/                    - List my groups + public groups
    - POST   /api/groups/                    - Create new group
    - GET    /api/groups/{id}/               - Get group details
    - PUT    /api/groups/{id}/               - Update group
    - DELETE /api/groups/{id}/               - Delete group
    - POST   /api/groups/{id}/add_members/   - Add members to group
    - POST   /api/groups/{id}/remove_members/ - Remove members from group
    - GET    /api/groups/by_type/            - List groups by type
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['group_type']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name', 'member_count']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Return the base queryset for this request.

        - `GET /api/groups/` and aggregate endpoints operate on the user's own groups.
        - Detail endpoints can access groups that are public or owned by the user.
        - Public discovery uses `GET /api/groups/public/`.
        """
        if self.action in {'list', 'by_type', 'summary'}:
            return GenericGroup.objects.filter(owner=self.request.user).select_related('owner')

        return GenericGroup.objects.filter(
            Q(owner=self.request.user) | Q(settings__visibility='public')
        ).select_related('owner')

    def _paginate_list_queryset(self, queryset):
        """
        Paginate and serialize a queryset using the list serializer.

        Returns a dict in DRF pagination format: {count, next, previous, results}.
        """
        serializer_class = GenericGroupListSerializer

        if not self.pagination_class:
            serializer = serializer_class(queryset, many=True)
            return {'count': len(serializer.data), 'next': None, 'previous': None, 'results': serializer.data}

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, self.request, view=self)
        if page is not None:
            serializer = serializer_class(page, many=True)
            return paginator.get_paginated_response(serializer.data).data

        serializer = serializer_class(queryset, many=True)
        return {'count': queryset.count(), 'next': None, 'previous': None, 'results': serializer.data}

    def list(self, request, *args, **kwargs):
        """
        List groups split into:
        - my_groups: groups owned by the authenticated user
        - public_groups: public groups owned by others (discoverable/subscribable)
        """
        my_groups = GenericGroup.objects.filter(owner=request.user).select_related('owner')
        public_groups = GenericGroup.objects.filter(settings__visibility='public').exclude(owner=request.user).select_related('owner')

        my_groups = self.filter_queryset(my_groups)
        public_groups = self.filter_queryset(public_groups)

        return Response(
            {
                'my_groups': self._paginate_list_queryset(my_groups),
                'public_groups': self._paginate_list_queryset(public_groups),
            },
            status=status.HTTP_200_OK,
        )

    def _require_owner(self, group: GenericGroup) -> None:
        if group.owner_id != self.request.user.id:
            raise PermissionDenied("Only the group owner can modify this group")

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return GenericGroupListSerializer
        elif self.action == 'create':
            return GenericGroupCreateSerializer
        return GenericGroupSerializer

    def perform_create(self, serializer):
        """Create group with current user as owner."""
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        self._require_owner(self.get_object())
        serializer.save()

    def perform_destroy(self, instance):
        self._require_owner(instance)
        instance.delete()

    @action(detail=True, methods=['post'], url_path='add_members')
    def add_members(self, request, pk=None):
        """
        Add members to a group.

        Request body:
        {
            "members": [
                {"member_key": "ETH:mainnet:0x123...", "label": "Treasury", "tags": ["defi"]},
                {"member_key": "ETH:mainnet:0x456...", "label": "Hot Wallet"}
            ]
        }

        For AlertGroups, members must be in format 'template:{uuid}' and reference
        AlertTemplates with matching alert_type.
        """
        group = self.get_object()
        self._require_owner(group)

        # Pass group in context for AlertGroup member validation
        serializer = GroupMemberBulkSerializer(
            data=request.data,
            context={'group': group, 'request': request}
        )
        serializer.is_valid(raise_exception=True)

        members_data = serializer.validated_data['members']
        user_id = str(request.user.id)
        added_count = 0
        already_exists = []

        for member in members_data:
            member_key = member['member_key']
            if group.has_member(member_key):
                already_exists.append(member_key)
            else:
                success = group.add_member_local(
                    member_key=member_key,
                    added_by=user_id,
                    label=member.get('label', ''),
                    tags=member.get('tags', []),
                    metadata=member.get('metadata', {})
                )
                if success:
                    added_count += 1

        return Response({
            'added': added_count,
            'already_exists': already_exists,
            'total_members': group.member_count
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='update_members')
    def update_members(self, request, pk=None):
        """
        Update metadata for existing members.

        Request body:
        {
            "members": [
                {"member_key": "ETH:mainnet:0x123...", "label": "Treasury", "metadata": {"owner_verified": true}}
            ]
        }
        """
        group = self.get_object()
        self._require_owner(group)

        serializer = GroupMemberBulkUpdateSerializer(
            data=request.data,
            context={'group': group, 'request': request}
        )
        serializer.is_valid(raise_exception=True)

        members_data = serializer.validated_data['members']
        members_map = group.member_data.get('members', {})
        updated_count = 0
        not_found = []

        is_accounts_group = (
            group.group_type == GroupType.WALLET and group.settings.get('system_key') == SYSTEM_GROUP_ACCOUNTS
        )

        for member in members_data:
            raw_key = member['member_key']
            normalized_key = group.normalize_member_key(raw_key)

            if normalized_key not in members_map:
                not_found.append(raw_key)
                continue

            current_entry = members_map.get(normalized_key, {}) or {}

            if 'label' in member:
                current_entry['label'] = member.get('label', '')
            if 'tags' in member:
                current_entry['tags'] = member.get('tags', [])
            if 'metadata' in member:
                existing_metadata = current_entry.get('metadata', {}) or {}
                incoming_metadata = member.get('metadata', {}) or {}

                merged_metadata = {**existing_metadata, **incoming_metadata}
                if is_accounts_group:
                    merged_metadata = {
                        "owner_verified": bool(merged_metadata.get("owner_verified", False)),
                        **merged_metadata,
                    }

                current_entry['metadata'] = merged_metadata

            members_map[normalized_key] = current_entry
            updated_count += 1

        if updated_count:
            group.member_data['members'] = members_map
            group.save(update_fields=['member_data', 'updated_at'])

        return Response({
            'updated': updated_count,
            'not_found': not_found,
            'total_members': group.member_count,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='remove_members')
    def remove_members(self, request, pk=None):
        """
        Remove members from a group.

        Request body:
        {
            "members": [
                {"member_key": "ETH:mainnet:0x123..."},
                {"member_key": "ETH:mainnet:0x456..."}
            ]
        }
        """
        group = self.get_object()
        self._require_owner(group)

        serializer = GroupMemberBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        members_data = serializer.validated_data['members']
        removed_count = 0
        not_found = []

        for member in members_data:
            member_key = member['member_key']
            if group.has_member(member_key):
                success = group.remove_member_local(member_key)
                if success:
                    removed_count += 1
            else:
                not_found.append(member_key)

        return Response({
            'removed': removed_count,
            'not_found': not_found,
            'total_members': group.member_count
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='by_type')
    def by_type(self, request):
        """
        Filter groups by type.

        Query params:
        - type: Group type (wallet, alert, network, token, etc.)

        Example: GET /api/groups/by_type/?type=wallet
        """
        group_type = request.query_params.get('type')
        if not group_type:
            return Response(
                {'error': 'type parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_types = [choice[0] for choice in GroupType.choices]
        if group_type not in valid_types:
            return Response(
                {'error': f'Invalid type. Must be one of: {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        groups = self.get_queryset().filter(group_type=group_type)
        serializer = GenericGroupListSerializer(groups, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Get summary of user's groups by type.

        Returns counts and totals for each group type.
        """
        queryset = self.get_queryset()

        summary = {}
        for group_type, display_name in GroupType.choices:
            type_groups = queryset.filter(group_type=group_type)
            summary[group_type] = {
                'display_name': display_name,
                'count': type_groups.count(),
                'total_members': sum(g.member_count for g in type_groups)
            }

        return Response(summary)

    @action(detail=False, methods=['get'], url_path='public')
    def public(self, request):
        """List public groups (discoverable/subscribable groups)."""
        groups = GenericGroup.objects.filter(
            settings__visibility='public'
        ).select_related('owner')

        groups = self.filter_queryset(groups)
        page = self.paginate_queryset(groups)
        if page is not None:
            serializer = GenericGroupListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = GenericGroupListSerializer(groups, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='accounts')
    def accounts(self, request):
        """Get the user's Accounts group (if it exists)."""
        group = GenericGroup.objects.filter(
            owner=request.user,
            group_type=GroupType.WALLET,
            settings__system_key='accounts',
        ).first()
        if not group:
            return Response({'detail': 'Accounts group not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = GenericGroupSerializer(group)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='accounts/add_wallet')
    def accounts_add_wallet(self, request):
        """Add a wallet to the user's Accounts group (creates the group if missing)."""
        serializer = AccountsWalletAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        had_accounts_group = GenericGroup.objects.filter(
            owner=request.user,
            group_type=GroupType.WALLET,
            settings__system_key='accounts',
        ).exists()
        had_legacy_default_group = GenericGroup.objects.filter(
            owner=request.user,
            group_type=GroupType.WALLET,
            settings__is_default=True,
        ).exists()

        accounts_group = GenericGroup.get_or_create_accounts_group(request.user)
        created = not had_accounts_group and not had_legacy_default_group

        # Ensure a Wallet DB row exists for this wallet_key.
        # Wallet uniqueness is per (network, subnet, address).
        from blockchain.models import Blockchain, Wallet

        member_key = serializer.validated_data['member_key']
        parts = [p.strip() for p in str(member_key).split(":") if p.strip()]
        network = parts[0].upper()
        subnet = parts[1].lower()
        address = ":".join(parts[2:])

        blockchain, _ = Blockchain.objects.get_or_create(
            symbol=network,
            defaults={"name": None},
        )
        wallet, wallet_created = Wallet.objects.get_or_create(
            blockchain=blockchain,
            subnet=subnet,
            address=address,
            defaults={"name": ""},
        )
        wallet_id = str(wallet.id)

        added = accounts_group.add_member_local(
            member_key=serializer.validated_data['member_key'],
            added_by=str(request.user.id),
            label=serializer.validated_data.get('label', ''),
            metadata={'owner_verified': serializer.validated_data.get('owner_verified', False)},
        )

        return Response({
            'group_id': str(accounts_group.id),
            'created': bool(created),
            'added': bool(added),
            'wallet_id': wallet_id,
            'wallet_created': bool(wallet_created),
            'total_members': accounts_group.member_count,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='accounts/add_wallets')
    def accounts_add_wallets(self, request):
        """
        Bulk-add wallets to the user's Accounts group (creates the group if missing).

        Unlike `accounts_add_wallet`, this endpoint is designed for batch imports and
        supports partial success with per-row error reporting.
        """
        serializer = AccountsWalletBulkAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        had_accounts_group = GenericGroup.objects.filter(
            owner=request.user,
            group_type=GroupType.WALLET,
            settings__system_key=SYSTEM_GROUP_ACCOUNTS,
        ).exists()
        had_legacy_default_group = GenericGroup.objects.filter(
            owner=request.user,
            group_type=GroupType.WALLET,
            settings__is_default=True,
        ).exists()

        accounts_group = GenericGroup.get_or_create_accounts_group(request.user)
        created = not had_accounts_group and not had_legacy_default_group

        from blockchain.models import Blockchain, Wallet

        members = (accounts_group.member_data or {}).get('members', {}) or {}
        errors: list[dict[str, object]] = []
        already_exists: list[str] = []
        added = 0
        wallet_rows_created = 0

        now_iso = timezone.now().isoformat()

        for idx, wallet_payload in enumerate(serializer.validated_data['wallets']):
            item = AccountsWalletAddSerializer(data=wallet_payload)
            if not item.is_valid():
                errors.append(
                    {
                        'row_number': idx + 1,
                        'member_key': str(wallet_payload.get('member_key', '')).strip(),
                        'errors': item.errors,
                    }
                )
                continue

            member_key = item.validated_data['member_key']
            normalized_key = accounts_group.normalize_member_key(member_key)

            if normalized_key in members:
                already_exists.append(normalized_key)
                continue

            parts = [p.strip() for p in str(normalized_key).split(":") if p.strip()]
            if len(parts) != 3:
                errors.append(
                    {
                        'row_number': idx + 1,
                        'member_key': str(wallet_payload.get('member_key', '')).strip(),
                        'errors': {'member_key': ['Invalid wallet key format']},
                    }
                )
                continue

            network, subnet, address = parts[0].upper(), parts[1].lower(), parts[2]

            blockchain, _ = Blockchain.objects.get_or_create(
                symbol=network,
                defaults={"name": None},
            )
            _, wallet_created = Wallet.objects.get_or_create(
                blockchain=blockchain,
                subnet=subnet,
                address=address,
                defaults={"name": ""},
            )
            if wallet_created:
                wallet_rows_created += 1

            label = str(item.validated_data.get('label', '') or '').strip()
            owner_verified = bool(item.validated_data.get('owner_verified', False))

            members[normalized_key] = {
                'added_at': now_iso,
                'added_by': str(request.user.id),
                'label': label,
                'tags': [],
                'metadata': {'owner_verified': owner_verified},
            }
            added += 1

        accounts_group.member_data = accounts_group.member_data or {}
        accounts_group.member_data['members'] = members
        accounts_group.member_count = len(members)
        accounts_group.save(update_fields=['member_data', 'member_count', 'updated_at'])

        return Response(
            {
                'group_id': str(accounts_group.id),
                'created': bool(created),
                'added': int(added),
                'already_exists': already_exists,
                'wallet_rows_created': int(wallet_rows_created),
                'errors': errors,
                'total_members': accounts_group.member_count,
            },
            status=status.HTTP_200_OK,
        )

    # ---------------------------------------------------------------------
    # USER WALLET GROUPS (Provider-Managed)
    # ---------------------------------------------------------------------

    def _normalize_wallet_key(self, raw_key: str) -> str:
        normalized = normalize_network_subnet_address_key(raw_key.strip())
        AlertValidationService.validate_targets('wallet', [normalized])
        return normalized

    def _parse_wallet_import_payload(self, fmt: str, payload: str) -> List[Tuple[int, str]]:
        items: list[tuple[int, str]] = []

        def _cell(value) -> str:
            # csv.DictReader uses None for missing columns; treat it as empty.
            if value is None:
                return ""
            return str(value).strip()

        if fmt == 'json':
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSON payload: {exc}") from exc

            if isinstance(parsed, dict):
                parsed = parsed.get('wallets', [])

            if not isinstance(parsed, list):
                raise ValidationError("JSON payload must be a list or an object with a 'wallets' list")

            for idx, item in enumerate(parsed, start=1):
                if isinstance(item, str):
                    items.append((idx, item))
                    continue
                if isinstance(item, dict):
                    if item.get('member_key'):
                        items.append((idx, str(item['member_key'])))
                        continue
                    network = _cell(item.get('network', ''))
                    subnet = _cell(item.get('subnet', ''))
                    address = _cell(item.get('address', ''))
                    if network and subnet and address:
                        items.append((idx, f"{network}:{subnet}:{address}"))
                        continue
                items.append((idx, ''))
            return items

        reader = csv.DictReader(io.StringIO(payload))
        if not reader.fieldnames:
            raise ValidationError("CSV payload must include a header row")

        for idx, row in enumerate(reader, start=1):
            if row.get('member_key'):
                items.append((idx, str(row['member_key'])))
                continue
            network = _cell(row.get('network', ''))
            subnet = _cell(row.get('subnet', ''))
            address = _cell(row.get('address', ''))
            if network and subnet and address:
                items.append((idx, f"{network}:{subnet}:{address}"))
            else:
                items.append((idx, ''))

        return items

    def _get_user_wallet_group(self, request, uwg_id: str) -> UserWalletGroup:
        return get_object_or_404(UserWalletGroup, id=uwg_id)

    def _ensure_user_wallet_group_editable(self, request, uwg: UserWalletGroup) -> None:
        if request.user == uwg.user:
            return
        if not uwg.can_edit(user=request.user):
            raise PermissionDenied("You do not have permission to modify this provider wallet group.")

    def _normalize_existing_wallet_keys(self, wallet_keys: List[str]) -> List[str]:
        normalized = []
        for key in wallet_keys:
            if not isinstance(key, str) or not key.strip():
                continue
            try:
                normalized.append(self._normalize_wallet_key(key))
            except Exception:
                normalized.append(key)
        return normalized

    @action(detail=False, methods=['get', 'post'], url_path='user-wallet-groups')
    def user_wallet_groups(self, request):
        """List provider-managed wallet groups for the authenticated user or create one."""
        if request.method == 'POST':
            serializer = UserWalletGroupCreateSerializer(
                data=request.data,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            uwg = serializer.save()
            response_serializer = UserWalletGroupSerializer(uwg, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        qs = UserWalletGroup.objects.filter(user=request.user).select_related(
            'wallet_group',
            'provider',
            'callback',
        ).order_by('-created_at')

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = UserWalletGroupSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = UserWalletGroupSerializer(qs, many=True, context={'request': request})
        return Response({
            'count': qs.count(),
            'next': None,
            'previous': None,
            'results': serializer.data,
        }, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['get', 'patch', 'delete'],
        url_path=r'user-wallet-groups/(?P<uwg_id>[^/.]+)',
    )
    def user_wallet_group_detail(self, request, uwg_id=None):
        """Retrieve/update/delete a provider-managed wallet group membership for the authenticated user."""
        uwg = get_object_or_404(UserWalletGroup, id=uwg_id, user=request.user)

        if request.method == 'GET':
            serializer = UserWalletGroupSerializer(uwg, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        if request.method == 'PATCH':
            serializer = UserWalletGroupUpdateSerializer(
                uwg,
                data=request.data,
                partial=True,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            response_serializer = UserWalletGroupSerializer(uwg, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        # DELETE
        uwg.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['post'],
        url_path=r'user-wallet-groups/(?P<uwg_id>[^/.]+)/add_wallets',
    )
    def user_wallet_group_add_wallets(self, request, uwg_id=None):
        """Add wallet keys to a provider-managed wallet group."""
        uwg = self._get_user_wallet_group(request, uwg_id)
        self._ensure_user_wallet_group_editable(request, uwg)

        serializer = UserWalletGroupWalletKeysSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        normalized_keys = serializer.validated_data['wallet_keys']
        dedupe = serializer.validated_data.get('dedupe', True)

        existing_keys = self._normalize_existing_wallet_keys(list(uwg.wallet_keys or []))
        existing_set = set(existing_keys)
        added = []
        duplicates = []

        for key in normalized_keys:
            if key in existing_set:
                duplicates.append(key)
                continue
            existing_keys.append(key)
            existing_set.add(key)
            added.append(key)

        if dedupe:
            seen = set()
            unique_keys = []
            for key in existing_keys:
                if key in seen:
                    continue
                seen.add(key)
                unique_keys.append(key)
            existing_keys = unique_keys

        uwg.wallet_keys = existing_keys
        uwg.save(update_fields=['wallet_keys', 'updated_at'])

        return Response(
            {
                'id': str(uwg.id),
                'added': added,
                'duplicates': duplicates,
                'total_wallets': len(uwg.wallet_keys or []),
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path=r'user-wallet-groups/(?P<uwg_id>[^/.]+)/remove_wallets',
    )
    def user_wallet_group_remove_wallets(self, request, uwg_id=None):
        """Remove wallet keys from a provider-managed wallet group."""
        uwg = self._get_user_wallet_group(request, uwg_id)
        self._ensure_user_wallet_group_editable(request, uwg)

        serializer = UserWalletGroupWalletKeysSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        normalized_keys = serializer.validated_data['wallet_keys']

        existing_keys = self._normalize_existing_wallet_keys(list(uwg.wallet_keys or []))
        existing_set = set(existing_keys)
        removed = []
        not_found = []

        for key in normalized_keys:
            if key in existing_set:
                existing_set.remove(key)
                removed.append(key)
            else:
                not_found.append(key)

        uwg.wallet_keys = [key for key in existing_keys if key in existing_set]
        uwg.save(update_fields=['wallet_keys', 'updated_at'])

        return Response(
            {
                'id': str(uwg.id),
                'removed': removed,
                'not_found': not_found,
                'total_wallets': len(uwg.wallet_keys or []),
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path=r'user-wallet-groups/(?P<uwg_id>[^/.]+)/import_wallets',
    )
    def user_wallet_group_import_wallets(self, request, uwg_id=None):
        """Bulk import wallet keys into a provider-managed wallet group."""
        uwg = self._get_user_wallet_group(request, uwg_id)
        self._ensure_user_wallet_group_editable(request, uwg)

        serializer = UserWalletGroupImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fmt = serializer.validated_data['format']
        payload = serializer.validated_data['payload']
        merge_mode = serializer.validated_data.get('merge_mode', 'append')
        dedupe = serializer.validated_data.get('dedupe', True)

        parsed_items = self._parse_wallet_import_payload(fmt, payload)

        added = []
        duplicates = []
        invalid = []
        errors = []
        seen_payload = set()

        if merge_mode == 'replace':
            base_keys = []
            existing_set = set()
        else:
            base_keys = self._normalize_existing_wallet_keys(list(uwg.wallet_keys or []))
            existing_set = set(base_keys)

        for row_number, raw_key in parsed_items:
            if not raw_key.strip():
                invalid.append(row_number)
                errors.append({'row_number': row_number, 'error': 'Missing wallet key'})
                continue

            try:
                normalized = self._normalize_wallet_key(raw_key)
            except Exception as exc:
                invalid.append(row_number)
                errors.append({'row_number': row_number, 'error': str(exc)})
                continue

            if dedupe and normalized in seen_payload:
                duplicates.append(normalized)
                continue
            seen_payload.add(normalized)

            if normalized in existing_set:
                duplicates.append(normalized)
                continue

            base_keys.append(normalized)
            existing_set.add(normalized)
            added.append(normalized)

        if dedupe:
            unique_keys = []
            seen = set()
            for key in base_keys:
                if key in seen:
                    continue
                seen.add(key)
                unique_keys.append(key)
            base_keys = unique_keys

        uwg.wallet_keys = base_keys
        uwg.save(update_fields=['wallet_keys', 'updated_at'])

        return Response(
            {
                'id': str(uwg.id),
                'merge_mode': merge_mode,
                'added': added,
                'duplicates': duplicates,
                'invalid_rows': invalid,
                'errors': errors,
                'total_wallets': len(uwg.wallet_keys or []),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], url_path='members')
    def list_members(self, request, pk=None):
        """
        Get all members of a group with their metadata.

        Returns member keys with full metadata including labels, tags, and timestamps.
        """
        group = self.get_object()
        members = group.member_data.get('members', {})

        return Response({
            'group_id': str(group.id),
            'group_name': group.name,
            'member_count': group.member_count,
            'members': members
        })

    @action(detail=True, methods=['get'], url_path='templates')
    def templates(self, request, pk=None):
        """
        List AlertTemplates contained in an AlertGroup.

        This supports subscription UIs that need to render required parameters
        for all templates in an AlertGroup before subscribing.
        """
        group = self.get_object()
        if group.group_type != GroupType.ALERT:
            return Response(
                {'detail': 'Only AlertGroups have templates'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from app.services.group_service import GroupService
        from app.models.alert_templates import AlertTemplate

        template_ids = GroupService._extract_template_ids_from_alert_group(group)
        templates = AlertTemplate.objects.filter(id__in=template_ids).order_by('name')

        return Response({
            'alert_group_id': str(group.id),
            'alert_group_name': group.name,
            'alert_type': group.get_alert_type(),
            'templates': [
                {
                    'id': str(t.id),
                    'name': t.name,
                    'description': t.description,
                    'template_type': t.get_template_type(),
                    'alert_type': t.alert_type,
                    'variables': t.get_spec_variables(),
                }
                for t in templates
            ],
        })


class GroupSubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for GroupSubscription CRUD operations.

    Endpoints:
    - GET    /api/subscriptions/             - List user's subscriptions
    - POST   /api/subscriptions/             - Create subscription
    - GET    /api/subscriptions/{id}/        - Get subscription details
    - PUT    /api/subscriptions/{id}/        - Update subscription
    - DELETE /api/subscriptions/{id}/        - Delete subscription
    - POST   /api/subscriptions/{id}/toggle/ - Toggle subscription active status
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['alert_group', 'target_group', 'target_key', 'is_active']
    search_fields = ['alert_group__name', 'target_group__name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter to user's own subscriptions."""
        return GroupSubscription.objects.filter(
            owner=self.request.user
        ).select_related('alert_group', 'target_group', 'owner')

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return GroupSubscriptionListSerializer
        return GroupSubscriptionSerializer

    def perform_create(self, serializer):
        """Create subscription with current user as owner."""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, pk=None):
        """Toggle the active status of a subscription."""
        subscription = self.get_object()
        subscription.is_active = not subscription.is_active
        subscription.save(update_fields=['is_active', 'updated_at'])

        return Response({
            'id': str(subscription.id),
            'is_active': subscription.is_active,
            'message': f"Subscription {'activated' if subscription.is_active else 'deactivated'}"
        })

    @action(detail=False, methods=['get'], url_path='by_alert_group')
    def by_alert_group(self, request):
        """
        Get subscriptions for a specific alert group.

        Query params:
        - alert_group_id: UUID of the alert group
        """
        alert_group_id = request.query_params.get('alert_group_id')
        if not alert_group_id:
            return Response(
                {'error': 'alert_group_id parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscriptions = self.get_queryset().filter(alert_group_id=alert_group_id)
        serializer = GroupSubscriptionListSerializer(subscriptions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by_target_group')
    def by_target_group(self, request):
        """
        Get subscriptions for a specific target group.

        Query params:
        - target_group_id: UUID of the target group
        """
        target_group_id = request.query_params.get('target_group_id')
        if not target_group_id:
            return Response(
                {'error': 'target_group_id parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscriptions = self.get_queryset().filter(target_group_id=target_group_id)
        serializer = GroupSubscriptionListSerializer(subscriptions, many=True)
        return Response(serializer.data)
