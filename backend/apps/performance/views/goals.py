from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from ..models import Goal
from ..serializers import GoalCreateSerializer, GoalSerializer
from ._shared import _active_cycle


# ─── Goals (self-service) ───────────────────────────────────────────────────────

class MyGoalsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle = _active_cycle()
        if not cycle:
            return success('No active review cycle.', [])
        goals = Goal.objects.filter(employee=request.user, cycle=cycle)
        return success('Goals retrieved.', GoalSerializer(goals, many=True).data)

    def post(self, request):
        cycle = _active_cycle()
        if not cycle:
            return error('There is no active review cycle to add a goal to.', http_status=409)
        serializer = GoalCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        goal = serializer.save(employee=request.user, cycle=cycle, created_by=request.user)
        return success('Goal added.', GoalSerializer(goal).data, http_status=201)


class MyGoalDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_goal(self, pk, user):
        try:
            return Goal.objects.get(pk=pk, employee=user), None
        except Goal.DoesNotExist:
            return None, error('Goal not found.', http_status=404)

    def patch(self, request, pk):
        goal, err = self._get_goal(pk, request.user)
        if err:
            return err
        serializer = GoalCreateSerializer(goal, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        return success('Goal updated.', GoalSerializer(goal).data)

    def delete(self, request, pk):
        goal, err = self._get_goal(pk, request.user)
        if err:
            return err
        goal.delete()
        return success('Goal removed.')
