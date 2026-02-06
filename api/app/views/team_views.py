"""
Team management API views.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Team, TeamMember, TeamMemberRole

User = get_user_model()


def _get_membership(user, team_id):
    return TeamMember.objects.filter(team_id=team_id, user=user, is_active=True).first()


def _require_admin(user, team_id):
    membership = _get_membership(user, team_id)
    if not membership:
        return None, Response({"error": "Not a member of this team"}, status=status.HTTP_403_FORBIDDEN)
    if membership.role not in [TeamMemberRole.OWNER, TeamMemberRole.ADMIN]:
        return None, Response({"error": "Admin permissions required"}, status=status.HTTP_403_FORBIDDEN)
    return membership, None


class TeamListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        teams = Team.objects.filter(members__user=request.user, members__is_active=True).annotate(
            member_count=Count("members", filter=Q(members__is_active=True))
        ).order_by("name")

        results = []
        memberships = TeamMember.objects.filter(team__in=teams, user=request.user)
        role_by_team = {m.team_id: m.role for m in memberships}

        for team in teams:
            results.append({
                "id": str(team.id),
                "name": team.name,
                "slug": team.slug,
                "description": team.description,
                "role": role_by_team.get(team.id),
                "member_count": team.member_count,
                "max_members": team.max_members,
                "created_at": team.created_at.isoformat(),
            })

        return Response({"teams": results})


class TeamMembersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, team_id):
        membership = _get_membership(request.user, team_id)
        if not membership:
            return Response({"error": "Not a member of this team"}, status=status.HTTP_403_FORBIDDEN)

        members = TeamMember.objects.filter(team_id=team_id).select_related("user").order_by("-created_at")
        results = []
        for member in members:
            user = member.user
            results.append({
                "id": str(member.id),
                "name": user.full_name,
                "email": user.email,
                "role": member.role,
                "status": "active" if member.is_active else "pending",
                "joined_at": member.joined_at.isoformat(),
                "last_active_at": user.last_login.isoformat() if user.last_login else None,
            })

        return Response({"members": results})


class TeamInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, team_id):
        _, error_response = _require_admin(request.user, team_id)
        if error_response:
            return error_response

        email = request.data.get("email", "").strip().lower()
        role = request.data.get("role", TeamMemberRole.MEMBER)

        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)
        if role not in TeamMemberRole.values:
            return Response({"error": "invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        invited_user = User.objects.filter(email=email).first()
        if not invited_user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        membership = TeamMember.objects.filter(team_id=team_id, user=invited_user).first()
        if membership:
            return Response({"error": "User is already a team member"}, status=status.HTTP_400_BAD_REQUEST)

        membership = TeamMember.objects.create(
            team_id=team_id,
            user=invited_user,
            role=role,
            invited_by=request.user,
            is_active=True,
        )

        return Response({
            "member": {
                "id": str(membership.id),
                "name": invited_user.full_name,
                "email": invited_user.email,
                "role": membership.role,
                "status": "active",
                "joined_at": membership.joined_at.isoformat(),
                "last_active_at": invited_user.last_login.isoformat() if invited_user.last_login else None,
            }
        }, status=status.HTTP_201_CREATED)


class TeamMemberDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, team_id, member_id):
        _, error_response = _require_admin(request.user, team_id)
        if error_response:
            return error_response

        member = TeamMember.objects.filter(team_id=team_id, id=member_id).select_related("user").first()
        if not member:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        role = request.data.get("role")
        if role and role not in TeamMemberRole.values:
            return Response({"error": "invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        if role:
            member.role = role
        member.save(update_fields=["role", "updated_at"])

        return Response({
            "id": str(member.id),
            "name": member.user.full_name,
            "email": member.user.email,
            "role": member.role,
            "status": "active" if member.is_active else "pending",
            "joined_at": member.joined_at.isoformat(),
            "last_active_at": member.user.last_login.isoformat() if member.user.last_login else None,
        })

    def delete(self, request, team_id, member_id):
        _, error_response = _require_admin(request.user, team_id)
        if error_response:
            return error_response

        member = TeamMember.objects.filter(team_id=team_id, id=member_id).first()
        if not member:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamMemberResendInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, team_id, member_id):
        _, error_response = _require_admin(request.user, team_id)
        if error_response:
            return error_response

        member = TeamMember.objects.filter(team_id=team_id, id=member_id).select_related("user").first()
        if not member:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

        if member.is_active:
            return Response({"error": "Member is already active"}, status=status.HTTP_400_BAD_REQUEST)

        member.save(update_fields=["updated_at"])
        return Response({"message": "Invite resent"})
