"""
Django model factories for organization models
Uses factory_boy for consistent test data generation
"""
import factory
import uuid
from faker import Faker
from django.utils import timezone
from django.utils.text import slugify

from organizations.models import (
    Organization,
    Team,
    TeamMember,
    TeamMemberRole,
    UserSettings,
)

fake = Faker()


class OrganizationFactory(factory.django.DjangoModelFactory):
    """Factory for Organization model"""

    class Meta:
        model = Organization

    name = factory.Faker("company")
    slug = factory.LazyAttribute(lambda obj: f"{slugify(obj.name)}-{uuid.uuid4().hex[:8]}")  # Unique slug
    description = factory.Faker("text", max_nb_chars=300)
    max_teams = factory.Faker("random_int", min=5, max=50)
    max_users_per_team = factory.Faker("random_int", min=10, max=100)
    passkey_required = factory.Faker("boolean", chance_of_getting_true=30)


class TeamFactory(factory.django.DjangoModelFactory):
    """Factory for Team model"""

    class Meta:
        model = Team

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Faker("word")
    slug = factory.LazyAttribute(lambda obj: f"{slugify(obj.name)}-{uuid.uuid4().hex[:8]}")  # Unique slug
    description = factory.Faker("text", max_nb_chars=200)
    is_active = True
    max_members = factory.Faker("random_int", min=5, max=50)


class TeamMemberFactory(factory.django.DjangoModelFactory):
    """Factory for TeamMember model"""
    
    class Meta:
        model = TeamMember
    
    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory('tests.factories.auth_factories.UserFactory')
    role = factory.Iterator([choice[0] for choice in TeamMemberRole.choices])
    joined_at = factory.Faker("date_time_this_year", tzinfo=timezone.get_current_timezone())
    invited_by = factory.SubFactory('tests.factories.auth_factories.UserFactory')
    is_active = True


class UserSettingsFactory(factory.django.DjangoModelFactory):
    """Factory for UserSettings model"""
    
    class Meta:
        model = UserSettings
    
    user = factory.SubFactory('tests.factories.auth_factories.UserFactory')
    mute = factory.Faker("boolean", chance_of_getting_true=20)


# Utility functions for creating related objects
def create_organization_with_teams(team_count=3, **org_kwargs):
    """Create an organization with multiple teams"""
    organization = OrganizationFactory(**org_kwargs)
    
    teams = []
    for i in range(team_count):
        team = TeamFactory(
            organization=organization,
            name=f"Team {i+1}",
            slug=f"team-{i+1}"
        )
        teams.append(team)
    
    return organization, teams


def create_team_with_members(member_count=5, **team_kwargs):
    """Create a team with multiple members"""
    team = TeamFactory(**team_kwargs)
    
    # Create team owner
    owner = TeamMemberFactory(
        team=team,
        role=TeamMemberRole.OWNER,
        invited_by=None
    )
    
    # Create other members
    members = [owner]
    for i in range(member_count - 1):
        role = fake.random_element([
            TeamMemberRole.ADMIN,
            TeamMemberRole.MEMBER,
            TeamMemberRole.VIEWER
        ])
        member = TeamMemberFactory(
            team=team,
            role=role,
            invited_by=owner.user
        )
        members.append(member)
    
    return team, members


def create_complete_organization_structure(**org_kwargs):
    """Create a complete organization with teams and members"""
    organization = OrganizationFactory(**org_kwargs)
    
    # Create teams
    teams = []
    all_members = []
    
    for i in range(3):  # 3 teams
        team = TeamFactory(
            organization=organization,
            name=f"Team {i+1}",
            slug=f"team-{i+1}"
        )
        teams.append(team)
        
        # Create team members
        team_members = []
        
        # Team owner
        owner = TeamMemberFactory(
            team=team,
            role=TeamMemberRole.OWNER,
            invited_by=None
        )
        team_members.append(owner)
        
        # Team members
        for j in range(fake.random_int(2, 5)):
            role = fake.random_element([
                TeamMemberRole.ADMIN,
                TeamMemberRole.MEMBER,
                TeamMemberRole.VIEWER
            ])
            member = TeamMemberFactory(
                team=team,
                role=role,
                invited_by=owner.user
            )
            team_members.append(member)
        
        all_members.extend(team_members)
    
    return {
        'organization': organization,
        'teams': teams,
        'members': all_members,
    }


def create_user_with_organization_membership(role=TeamMemberRole.MEMBER):
    """Create a user with organization and team membership"""
    from tests.factories.auth_factories import UserFactory
    
    user = UserFactory()
    organization = OrganizationFactory()
    team = TeamFactory(organization=organization)
    
    membership = TeamMemberFactory(
        team=team,
        user=user,
        role=role
    )
    
    # Create user settings
    settings = UserSettingsFactory(user=user)
    
    return {
        'user': user,
        'organization': organization,
        'team': team,
        'membership': membership,
        'settings': settings,
    }


def create_multi_team_user():
    """Create a user who is a member of multiple teams"""
    from tests.factories.auth_factories import UserFactory
    
    user = UserFactory()
    
    memberships = []
    teams = []
    organizations = []
    
    # Create memberships in 3 different teams/organizations
    for i in range(3):
        org = OrganizationFactory()
        team = TeamFactory(organization=org)
        
        role = fake.random_element([
            TeamMemberRole.ADMIN,
            TeamMemberRole.MEMBER,
            TeamMemberRole.VIEWER
        ])
        
        membership = TeamMemberFactory(
            team=team,
            user=user,
            role=role
        )
        
        memberships.append(membership)
        teams.append(team)
        organizations.append(org)
    
    return {
        'user': user,
        'memberships': memberships,
        'teams': teams,
        'organizations': organizations,
    }


def create_organization_hierarchy():
    """Create a complex organization hierarchy for testing"""
    # Main organization
    org = OrganizationFactory(name="Ekko Technologies")
    
    # Engineering teams
    eng_team = TeamFactory(
        organization=org,
        name="Engineering",
        slug="engineering"
    )
    
    frontend_team = TeamFactory(
        organization=org,
        name="Frontend",
        slug="frontend"
    )
    
    backend_team = TeamFactory(
        organization=org,
        name="Backend",
        slug="backend"
    )
    
    # Product team
    product_team = TeamFactory(
        organization=org,
        name="Product",
        slug="product"
    )
    
    teams = [eng_team, frontend_team, backend_team, product_team]
    
    # Create team hierarchies with different roles
    all_members = []
    
    for team in teams:
        # Team lead (owner)
        lead = TeamMemberFactory(
            team=team,
            role=TeamMemberRole.OWNER,
            invited_by=None
        )
        
        # Senior members (admins)
        seniors = [
            TeamMemberFactory(
                team=team,
                role=TeamMemberRole.ADMIN,
                invited_by=lead.user
            ) for _ in range(2)
        ]
        
        # Regular members
        members = [
            TeamMemberFactory(
                team=team,
                role=TeamMemberRole.MEMBER,
                invited_by=lead.user
            ) for _ in range(fake.random_int(3, 7))
        ]
        
        # Viewers (contractors, interns)
        viewers = [
            TeamMemberFactory(
                team=team,
                role=TeamMemberRole.VIEWER,
                invited_by=fake.random_element(seniors).user
            ) for _ in range(fake.random_int(1, 3))
        ]
        
        team_members = [lead] + seniors + members + viewers
        all_members.extend(team_members)
    
    return {
        'organization': org,
        'teams': teams,
        'members': all_members,
        'team_structure': {
            'engineering': eng_team,
            'frontend': frontend_team,
            'backend': backend_team,
            'product': product_team,
        }
    }
