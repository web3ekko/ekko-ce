"""
Unit tests for Multi-Address Notification System API endpoints
Tests NotificationChannelEndpoint, TeamNotificationChannelEndpoint, and TeamMemberNotificationOverride ViewSets
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone

from app.models.notifications import (
    NotificationChannelEndpoint,
    TeamMemberNotificationOverride,
    NotificationChannelVerification,
)
from organizations.models import Organization, Team, TeamMember, TeamMemberRole

User = get_user_model()


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.django_db
class TestNotificationChannelEndpointAPI:
    """Test user notification endpoint API"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data for each test"""
        self.user = User.objects.create_user(
            email="endpoint_api@example.com",
            first_name="Endpoint",
            last_name="API"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            first_name="Other",
            last_name="User"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_user_endpoints(self):
        """Test listing user's notification endpoints"""
        # Create endpoints for authenticated user
        NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Personal Email',
            config={'address': 'user@example.com'},
            created_by=self.user
        )
        NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='telegram',
            label='Telegram',
            config={'chat_id': '123456'},
            created_by=self.user
        )

        # Create endpoint for other user (should not be visible)
        NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.other_user.id,
            channel_type='email',
            label='Other Email',
            config={'address': 'other@example.com'},
            created_by=self.other_user
        )

        response = self.client.get('/api/notifications/channels/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 2
        # Verify only user's endpoints are returned
        for endpoint in response.data['results']:
            assert endpoint['owner_id'] == str(self.user.id)

    def test_create_user_endpoint(self):
        """Test creating a new notification endpoint"""
        data = {
            'channel_type': 'email',
            'label': 'Personal Gmail',
            'config': {'address': 'user@gmail.com'},
            'enabled': True,
            'routing_mode': 'all_enabled',
            'priority_filters': []
        }

        response = self.client.post('/api/notifications/channels/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['channel_type'] == 'email'
        assert response.data['label'] == 'Personal Gmail'
        assert response.data['owner_type'] == 'user'
        assert response.data['owner_id'] == str(self.user.id)
        assert response.data['verified'] == False  # Email requires verification

        # Verify endpoint was created in database
        endpoint = NotificationChannelEndpoint.objects.get(id=response.data['id'])
        assert endpoint.created_by == self.user

    def test_create_webhook_endpoint_auto_verifies(self):
        """Test that webhook endpoints are auto-verified"""
        data = {
            'channel_type': 'webhook',
            'label': 'Monitoring Webhook',
            'config': {'url': 'https://monitor.example.com/webhook'},
            'enabled': True
        }

        response = self.client.post('/api/notifications/channels/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['verified'] == True  # Webhook auto-verifies

    def test_update_endpoint(self):
        """Test updating an existing endpoint"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Work Email',
            config={'address': 'work@company.com'},
            created_by=self.user
        )

        data = {
            'label': 'Updated Work Email',
            'enabled': False
        }

        response = self.client.patch(
            f'/api/notifications/channels/{endpoint.id}/',
            data,
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['label'] == 'Updated Work Email'
        assert response.data['enabled'] == False

    def test_delete_endpoint(self):
        """Test deleting an endpoint"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Old Email',
            config={'address': 'old@example.com'},
            created_by=self.user
        )

        response = self.client.delete(f'/api/notifications/channels/{endpoint.id}/')

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not NotificationChannelEndpoint.objects.filter(id=endpoint.id).exists()

    def test_request_verification(self):
        """Test requesting verification code for endpoint"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Email',
            config={'address': 'user@example.com'},
            verified=False,
            created_by=self.user
        )

        response = self.client.post(
            f'/api/notifications/channels/{endpoint.id}/request_verification/'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert 'verification_id' in response.data
        assert 'expires_at' in response.data

        # Verify code was created
        verification = NotificationChannelVerification.objects.get(
            id=response.data['verification_id']
        )
        assert verification.endpoint == endpoint
        assert len(verification.verification_code) == 6

    def test_verify_endpoint(self):
        """Test verifying an endpoint with correct code"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Email',
            config={'address': 'user@example.com'},
            verified=False,
            created_by=self.user
        )

        verification = NotificationChannelVerification.objects.create(
            endpoint=endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        response = self.client.post(
            f'/api/notifications/channels/{endpoint.id}/verify/',
            {'verification_code': '123456'},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data

        # Verify endpoint is now verified
        endpoint.refresh_from_db()
        assert endpoint.verified == True

    def test_verify_endpoint_wrong_code(self):
        """Test verifying with wrong code fails"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.user.id,
            channel_type='email',
            label='Email',
            config={'address': 'user@example.com'},
            verified=False,
            created_by=self.user
        )

        NotificationChannelVerification.objects.create(
            endpoint=endpoint,
            verification_code='123456',
            verification_type='initial',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        response = self.client.post(
            f'/api/notifications/channels/{endpoint.id}/verify/',
            {'verification_code': '999999'},  # Wrong code
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_access_other_user_endpoint(self):
        """Test that users cannot access other users' endpoints"""
        other_endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='user',
            owner_id=self.other_user.id,
            channel_type='email',
            label='Other Email',
            config={'address': 'other@example.com'},
            created_by=self.other_user
        )

        response = self.client.get(f'/api/notifications/channels/{other_endpoint.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.django_db
class TestTeamNotificationChannelEndpointAPI:
    """Test team notification endpoint API"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data for each test"""
        self.owner = User.objects.create_user(
            email="owner@example.com",
            first_name="Owner",
            last_name="User"
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            first_name="Admin",
            last_name="User"
        )
        self.member = User.objects.create_user(
            email="member@example.com",
            first_name="Member",
            last_name="User"
        )

        self.organization = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Test Team",
            slug="test-team"
        )

        TeamMember.objects.create(
            team=self.team,
            user=self.owner,
            role=TeamMemberRole.OWNER
        )
        TeamMember.objects.create(
            team=self.team,
            user=self.admin,
            role=TeamMemberRole.ADMIN
        )
        TeamMember.objects.create(
            team=self.team,
            user=self.member,
            role=TeamMemberRole.MEMBER
        )

        self.client = APIClient()

    def test_owner_can_create_team_endpoint(self):
        """Test that team owners can create team endpoints"""
        self.client.force_authenticate(user=self.owner)

        data = {
            'owner_id': str(self.team.id),
            'channel_type': 'slack',
            'label': 'Team Slack',
            'config': {'webhook_url': 'https://hooks.slack.com/...'},
            'enabled': True
        }

        response = self.client.post('/api/team-notification-endpoints/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['owner_type'] == 'team'
        assert response.data['owner_id'] == str(self.team.id)

    def test_admin_can_create_team_endpoint(self):
        """Test that team admins can create team endpoints"""
        self.client.force_authenticate(user=self.admin)

        data = {
            'owner_id': str(self.team.id),
            'channel_type': 'slack',
            'label': 'Team Slack',
            'config': {'webhook_url': 'https://hooks.slack.com/...'},
            'enabled': True
        }

        response = self.client.post('/api/team-notification-endpoints/', data, format='json')

        assert response.status_code == status.HTTP_201_CREATED

    def test_member_cannot_create_team_endpoint(self):
        """Test that regular members cannot create team endpoints"""
        self.client.force_authenticate(user=self.member)

        data = {
            'owner_id': str(self.team.id),
            'channel_type': 'slack',
            'label': 'Team Slack',
            'config': {'webhook_url': 'https://hooks.slack.com/...'},
            'enabled': True
        }

        response = self.client.post('/api/team-notification-endpoints/', data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_member_can_view_team_endpoints(self):
        """Test that members can view team endpoints"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='team',
            owner_id=self.team.id,
            channel_type='slack',
            label='Team Slack',
            config={'webhook_url': 'https://hooks.slack.com/...'},
            created_by=self.owner
        )

        self.client.force_authenticate(user=self.member)
        response = self.client.get(f'/api/team-notification-endpoints/{endpoint.id}/')

        assert response.status_code == status.HTTP_200_OK
        # Config should be masked for non-admins
        assert 'webhook_url' in response.data['config']
        assert response.data['config']['webhook_url'] == '***'

    def test_admin_sees_full_config(self):
        """Test that admins see full endpoint config"""
        endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='team',
            owner_id=self.team.id,
            channel_type='slack',
            label='Team Slack',
            config={'webhook_url': 'https://hooks.slack.com/...'},
            created_by=self.owner
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/team-notification-endpoints/{endpoint.id}/')

        assert response.status_code == status.HTTP_200_OK
        # Admin should see full config
        assert response.data['config']['webhook_url'] == 'https://hooks.slack.com/...'


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.django_db
class TestTeamMemberNotificationOverrideAPI:
    """Test team member notification override API"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data for each test"""
        self.user = User.objects.create_user(
            email="override_api@example.com",
            first_name="Override",
            last_name="API"
        )

        self.organization = Organization.objects.create(
            name="Test Org",
            slug="test-org"
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Test Team",
            slug="test-team"
        )

        TeamMember.objects.create(
            team=self.team,
            user=self.user,
            role=TeamMemberRole.MEMBER
        )

        self.endpoint = NotificationChannelEndpoint.objects.create(
            owner_type='team',
            owner_id=self.team.id,
            channel_type='slack',
            label='Team Slack',
            config={'webhook_url': 'https://hooks.slack.com/...'},
            created_by=self.user
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_user_overrides(self):
        """Test listing user's notification overrides for all teams"""
        # Create override
        TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user,
            disabled_endpoints=[str(self.endpoint.id)]
        )

        response = self.client.get('/api/team-notification-overrides/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        # Find our team's override
        override = next(
            (o for o in response.data if o['team_id'] == str(self.team.id)),
            None
        )
        assert override is not None
        assert str(self.endpoint.id) in override['disabled_endpoints']

    def test_get_or_create_override_for_team(self):
        """Test getting override for specific team (creates if not exists)"""
        response = self.client.get(
            f'/api/team-notification-overrides/{self.team.id}/'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['team_id'] == str(self.team.id)
        assert response.data['member_id'] == str(self.user.id)
        assert response.data['team_notifications_enabled'] == True

    def test_update_override(self):
        """Test updating notification override"""
        override = TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user
        )

        data = {
            'disabled_endpoints': [str(self.endpoint.id)],
            'disabled_priorities': ['low', 'normal']
        }

        response = self.client.patch(
            f'/api/team-notification-overrides/{self.team.id}/',
            data,
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert str(self.endpoint.id) in response.data['disabled_endpoints']
        assert 'low' in response.data['disabled_priorities']

    def test_disable_all_team_notifications(self):
        """Test disabling all team notifications with master switch"""
        response = self.client.post(
            '/api/team-notification-overrides/disable_all_team_notifications/',
            {'team': str(self.team.id)},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify override was created/updated
        override = TeamMemberNotificationOverride.objects.get(
            team=self.team,
            member=self.user
        )
        assert override.team_notifications_enabled == False

    def test_enable_all_team_notifications(self):
        """Test enabling all team notifications"""
        # First disable
        TeamMemberNotificationOverride.objects.create(
            team=self.team,
            member=self.user,
            team_notifications_enabled=False
        )

        # Then enable
        response = self.client.post(
            '/api/team-notification-overrides/enable_all_team_notifications/',
            {'team': str(self.team.id)},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify override was updated
        override = TeamMemberNotificationOverride.objects.get(
            team=self.team,
            member=self.user
        )
        assert override.team_notifications_enabled == True
