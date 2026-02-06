import pytest
from django.contrib.auth import get_user_model


pytestmark = pytest.mark.django_db


class TestWalletNicknameViews:
    def test_crud_flow(self, api_client, user):
        api_client.force_authenticate(user=user)

        create = api_client.post(
            "/api/wallet-nicknames/",
            data={
                "wallet_address": "0xAbC0000000000000000000000000000000000000",
                "chain_id": 1,
                "custom_name": "Treasury",
                "notes": "Primary account",
            },
            format="json",
        )
        assert create.status_code == 201
        created = create.json()
        nickname_id = created["id"]
        assert created["wallet_address"] == "0xabc0000000000000000000000000000000000000"
        assert created["chain_id"] == 1
        assert created["custom_name"] == "Treasury"

        listing = api_client.get("/api/wallet-nicknames/")
        assert listing.status_code == 200
        ids = [row["id"] for row in listing.json()["results"]]
        assert nickname_id in ids

        patch = api_client.patch(
            f"/api/wallet-nicknames/{nickname_id}/",
            data={"custom_name": "Treasury v2"},
            format="json",
        )
        assert patch.status_code == 200
        assert patch.json()["custom_name"] == "Treasury v2"

        delete = api_client.delete(f"/api/wallet-nicknames/{nickname_id}/")
        assert delete.status_code == 204

        listing2 = api_client.get("/api/wallet-nicknames/")
        assert listing2.status_code == 200
        assert listing2.json()["results"] == []

    def test_unique_constraint_per_user_address_chain(self, api_client, user):
        api_client.force_authenticate(user=user)

        first = api_client.post(
            "/api/wallet-nicknames/",
            data={
                "wallet_address": "0xabc0000000000000000000000000000000000000",
                "chain_id": 1,
                "custom_name": "One",
            },
            format="json",
        )
        assert first.status_code == 201

        dup = api_client.post(
            "/api/wallet-nicknames/",
            data={
                "wallet_address": "0xAbC0000000000000000000000000000000000000",
                "chain_id": 1,
                "custom_name": "Two",
            },
            format="json",
        )
        assert dup.status_code == 400

    def test_user_isolation(self, api_client, user):
        User = get_user_model()
        other = User.objects.create_user(
            email="other@example.com",
            first_name="Other",
            last_name="User",
            password="testpass123",
        )

        api_client.force_authenticate(user=other)
        created = api_client.post(
            "/api/wallet-nicknames/",
            data={
                "wallet_address": "0xabc0000000000000000000000000000000000000",
                "chain_id": 1,
                "custom_name": "Other",
            },
            format="json",
        )
        assert created.status_code == 201
        other_id = created.json()["id"]

        api_client.force_authenticate(user=user)
        listing = api_client.get("/api/wallet-nicknames/")
        assert listing.status_code == 200
        assert listing.json()["results"] == []

        detail = api_client.get(f"/api/wallet-nicknames/{other_id}/")
        assert detail.status_code == 404
