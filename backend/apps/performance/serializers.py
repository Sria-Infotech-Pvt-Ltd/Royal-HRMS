from rest_framework import serializers

from .models import Goal, PerformanceReview, ReviewCycle


class ReviewCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReviewCycle
        fields = [
            'id', 'name', 'period_start', 'period_end',
            'self_review_due', 'manager_review_due', 'status',
            'created_at', 'updated_at',
        ]


class ReviewCycleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReviewCycle
        fields = ['name', 'period_start', 'period_end', 'self_review_due', 'manager_review_due']

    def validate(self, attrs):
        if attrs['period_end'] <= attrs['period_start']:
            raise serializers.ValidationError({'period_end': 'Must be after the period start.'})
        if attrs['self_review_due'] > attrs['period_end']:
            raise serializers.ValidationError({'self_review_due': 'Must be on or before the period end.'})
        if attrs['manager_review_due'] < attrs['self_review_due']:
            raise serializers.ValidationError({'manager_review_due': 'Must be on or after the self-review due date.'})
        return attrs


class GoalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model  = Goal
        fields = [
            'id', 'employee', 'employee_name', 'cycle', 'title', 'description',
            'target_metric', 'due_date', 'status', 'weight_percent',
            'self_rating', 'outcome_measure', 'evidence_reference', 'self_comments',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'employee', 'employee_name', 'cycle', 'created_at', 'updated_at']


class GoalCreateSerializer(serializers.ModelSerializer):
    """Used by the employee's own goal create/update endpoints
    (MyGoalsView, MyGoalDetailView) — both already scope to
    `employee=request.user`, so the self-review fields here are only ever
    writable by the goal's own employee, matching the mockup's per-goal
    self-review sub-cards. `weight_percent` is included so an HR-driven
    goal-setting flow can set it later, but nothing in this app currently
    writes it from an admin surface."""
    class Meta:
        model  = Goal
        fields = [
            'title', 'description', 'target_metric', 'due_date', 'status', 'weight_percent',
            'self_rating', 'outcome_measure', 'evidence_reference', 'self_comments',
        ]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Title is required.')
        return value


class PerformanceReviewSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_id', read_only=True)
    cycle_name    = serializers.CharField(source='cycle.name', read_only=True)
    cycle_self_review_due    = serializers.DateField(source='cycle.self_review_due', read_only=True)
    cycle_manager_review_due = serializers.DateField(source='cycle.manager_review_due', read_only=True)
    manager_name  = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    activity_history = serializers.SerializerMethodField()

    class Meta:
        model  = PerformanceReview
        fields = [
            'id', 'employee', 'employee_name', 'employee_code', 'cycle', 'cycle_name',
            'cycle_self_review_due', 'cycle_manager_review_due',
            'metric_reference', 'what_changed', 'key_strengths', 'development_areas',
            'support_needed', 'next_cycle_goal', 'self_rating', 'self_submitted_at',
            'manager', 'manager_name', 'manager_rating', 'manager_notes', 'manager_submitted_at',
            'hr_calibrated_at', 'published_at', 'acknowledged_at',
            'status', 'status_display', 'activity_history', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'employee', 'employee_name', 'employee_code', 'cycle', 'cycle_name',
            'cycle_self_review_due', 'cycle_manager_review_due',
            'self_submitted_at', 'manager', 'manager_name', 'manager_submitted_at',
            'hr_calibrated_at', 'published_at', 'acknowledged_at',
            'status', 'status_display', 'activity_history', 'created_at', 'updated_at',
        ]

    def get_manager_name(self, obj: PerformanceReview) -> str:
        return obj.manager.full_name if obj.manager_id else ''

    def get_activity_history(self, obj: PerformanceReview) -> list:
        """Lightweight, derived-only activity feed — no separate audit
        model, just the timestamped milestones already on the cycle and
        this review, in chronological order. Raw ISO timestamps are sent
        as-is; the frontend formats them (see formatDate/formatDateTime)."""
        entries = [
            {'label': 'Cycle opened', 'actor': 'HR Operations', 'at': obj.cycle.created_at},
        ]
        if obj.self_submitted_at:
            entries.append({'label': 'Self-review submitted', 'actor': obj.employee.full_name, 'at': obj.self_submitted_at})
        if obj.manager_submitted_at:
            entries.append({'label': 'Manager review submitted', 'actor': obj.manager.full_name if obj.manager_id else 'Manager', 'at': obj.manager_submitted_at})
        if obj.hr_calibrated_at:
            entries.append({'label': 'HR calibration completed', 'actor': 'HR Operations', 'at': obj.hr_calibrated_at})
        if obj.published_at:
            entries.append({'label': 'Outcome published', 'actor': 'HR Operations', 'at': obj.published_at})
        if obj.acknowledged_at:
            entries.append({'label': 'Outcome acknowledged', 'actor': obj.employee.full_name, 'at': obj.acknowledged_at})
        entries.sort(key=lambda e: e['at'])
        return entries


class SelfReviewSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PerformanceReview
        fields = [
            'metric_reference', 'what_changed', 'key_strengths',
            'development_areas', 'support_needed', 'next_cycle_goal', 'self_rating',
        ]


class ManagerReviewSaveSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PerformanceReview
        fields = ['manager_rating', 'manager_notes']
