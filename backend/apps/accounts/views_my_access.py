"""
What the signed-in person may do ({permissions, can_manage_team, can_manage_branch, is_superuser}), read fresh from the server.

Why it exists: while someone looks at an employee's workspace ("View as employee", read-only) every request answers as that
employee (see authentication.py), but the login session still describes the person looking. The page asks this endpoint to
learn what the employee really has, so the top bar and the search box offer only the pages that employee could open.
Read-only, and nobody gains anything from it: it returns exactly what the same person's login already returned.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services_session import access_summary
from core.responses import success


class MyAccessView(APIView):
    """GET /api/employees/me/access/ - the caller's (or, when viewing as an employee, that employee's) permissions."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success('Access loaded.', access_summary(request.user))
