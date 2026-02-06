"""
Wallet nickname CRUD API.

Wallet nicknames are user-scoped custom labels for wallet addresses on a chain.
They are used for notification personalization (fallback after Accounts labels).
"""

from __future__ import annotations

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from app.serializers.wallet_nickname_serializers import WalletNicknameSerializer
from blockchain.models_wallet_nicknames import WalletNickname


class WalletNicknameViewSet(viewsets.ModelViewSet):
    """CRUD endpoints for the authenticated user's wallet nicknames."""

    serializer_class = WalletNicknameSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["custom_name", "wallet_address", "notes"]
    ordering_fields = ["created_at", "updated_at", "custom_name", "chain_id"]
    ordering = ["-created_at"]
    filterset_fields = ["chain_id"]

    def get_queryset(self) -> QuerySet[WalletNickname]:
        """
        Restrict nicknames to the authenticated user.

        Supports an additional alias query param `chain` for filtering by `chain_id`.
        """
        qs = WalletNickname.objects.filter(user=self.request.user)
        chain_param = self.request.query_params.get("chain")
        if chain_param is None:
            return qs

        try:
            chain_id = int(str(chain_param).strip())
        except (TypeError, ValueError):
            return qs.none()

        return qs.filter(chain_id=chain_id)
