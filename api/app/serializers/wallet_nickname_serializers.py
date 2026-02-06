from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from blockchain.models_wallet_nicknames import WalletNickname


class WalletNicknameSerializer(serializers.ModelSerializer):
    """Serializer for wallet nickname CRUD endpoints."""

    class Meta:
        model = WalletNickname
        fields = [
            "id",
            "wallet_address",
            "chain_id",
            "custom_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data: dict[str, Any]) -> WalletNickname:
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            raise serializers.ValidationError({"detail": "Authentication required"})

        instance = WalletNickname(user=request.user, **validated_data)
        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, "message_dict", {"detail": exc.messages}))
        return instance

    def update(self, instance: WalletNickname, validated_data: dict[str, Any]) -> WalletNickname:
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, "message_dict", {"detail": exc.messages}))
        return instance
