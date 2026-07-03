import re

from rest_framework import serializers

from .models import Assessment, AssessmentItem, CandidateAssignment, CandidateResponse


def _to_embed_url(url: str) -> str:
    """Convert any YouTube URL variant to an embeddable URL."""
    if not url:
        return url
    # Already in embed format
    if 'youtube.com/embed/' in url:
        return url
    # youtu.be/VIDEO_ID  or  youtu.be/VIDEO_ID?si=...
    match = re.match(r'https?://youtu\.be/([A-Za-z0-9_-]+)', url)
    if match:
        return f'https://www.youtube.com/embed/{match.group(1)}'
    # youtube.com/watch?v=VIDEO_ID
    match = re.match(r'https?://(?:www\.)?youtube\.com/watch\?.*?v=([A-Za-z0-9_-]+)', url)
    if match:
        return f'https://www.youtube.com/embed/{match.group(1)}'
    return url


# ─── HR-facing serializers ────────────────────────────────────────────────────

class AssessmentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AssessmentItem
        fields = [
            'id', 'item_type', 'title', 'order',
            'video_url', 'duration_secs',
            'question', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'pass_score', 'created_at',
        ]


class AssessmentItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AssessmentItem
        fields = [
            'item_type', 'title', 'order',
            'video_url', 'duration_secs',
            'question', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'pass_score',
        ]

    def validate(self, attrs):
        item_type = attrs.get('item_type')
        if item_type == AssessmentItem.TYPE_VIDEO:
            if not attrs.get('video_url'):
                raise serializers.ValidationError({'video_url': 'video_url is required for video items.'})
        elif item_type == AssessmentItem.TYPE_QUIZ:
            for field in ('question', 'option_a', 'option_b', 'correct_option'):
                if not attrs.get(field, '').strip():
                    raise serializers.ValidationError({field: f'{field} is required for quiz items.'})
            if attrs.get('correct_option', '') not in ('a', 'b', 'c', 'd'):
                raise serializers.ValidationError({'correct_option': 'Must be a, b, c, or d.'})
        return attrs


class AssessmentSerializer(serializers.ModelSerializer):
    items             = AssessmentItemSerializer(many=True, read_only=True)
    item_count        = serializers.SerializerMethodField()
    assigned_count    = serializers.SerializerMethodField()
    pending_count     = serializers.SerializerMethodField()
    in_progress_count = serializers.SerializerMethodField()
    completed_count   = serializers.SerializerMethodField()
    candidates        = serializers.SerializerMethodField()

    class Meta:
        model  = Assessment
        fields = [
            'id', 'title', 'description', 'is_active', 'is_default',
            'item_count', 'assigned_count', 'pending_count',
            'in_progress_count', 'completed_count',
            'candidates', 'items', 'created_at',
        ]

    def get_item_count(self, obj: Assessment) -> int:
        return obj.items.count()

    def get_assigned_count(self, obj: Assessment) -> int:
        return obj.assignments.count()

    def get_pending_count(self, obj: Assessment) -> int:
        return obj.assignments.filter(status=CandidateAssignment.STATUS_PENDING).count()

    def get_in_progress_count(self, obj: Assessment) -> int:
        return obj.assignments.filter(status=CandidateAssignment.STATUS_IN_PROGRESS).count()

    def get_completed_count(self, obj: Assessment) -> int:
        return obj.assignments.filter(status=CandidateAssignment.STATUS_COMPLETE).count()

    def get_candidates(self, obj: Assessment):
        assignments = obj.assignments.select_related('candidate').order_by('-created_at')
        return AssessmentCandidateSerializer(assignments, many=True).data


class AssessmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Assessment
        fields = ['title', 'description', 'is_active', 'is_default']

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError('Title cannot be blank.')
        return value.strip()


# ─── Portal-facing serializers (correct_option excluded) ─────────────────────

class PortalItemSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()

    class Meta:
        model  = AssessmentItem
        fields = [
            'id', 'item_type', 'title', 'order',
            'video_url', 'duration_secs',
            'question', 'option_a', 'option_b', 'option_c', 'option_d',
            'pass_score',
        ]

    def get_video_url(self, obj: AssessmentItem) -> str:
        return _to_embed_url(obj.video_url)


class CandidateResponseSerializer(serializers.ModelSerializer):
    item_id   = serializers.UUIDField(source='item.id',        read_only=True)
    item_type = serializers.CharField(source='item.item_type', read_only=True)

    class Meta:
        model  = CandidateResponse
        fields = [
            'id', 'item_id', 'item_type',
            'is_watched', 'selected_option', 'is_correct',
            'score_awarded', 'responded_at',
        ]


class PortalAssignmentSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    items            = serializers.SerializerMethodField()
    responses        = CandidateResponseSerializer(many=True, read_only=True)
    total_items      = serializers.SerializerMethodField()
    completed_items  = serializers.SerializerMethodField()

    class Meta:
        model  = CandidateAssignment
        fields = [
            'id', 'assessment_title', 'status',
            'score', 'max_score', 'total_items', 'completed_items',
            'completed_at', 'items', 'responses',
        ]

    def get_items(self, obj: CandidateAssignment):
        return PortalItemSerializer(obj.assessment.items.all(), many=True).data

    def get_total_items(self, obj: CandidateAssignment) -> int:
        return obj.assessment.items.count()

    def get_completed_items(self, obj: CandidateAssignment) -> int:
        all_items     = list(obj.assessment.items.all())
        video_ids     = {item.id for item in all_items if item.item_type == AssessmentItem.TYPE_VIDEO}
        quiz_ids      = {item.id for item in all_items if item.item_type == AssessmentItem.TYPE_QUIZ}
        all_responses = list(obj.responses.all())
        watched       = sum(1 for r in all_responses if r.item_id in video_ids and r.is_watched)
        answered      = sum(1 for r in all_responses if r.item_id in quiz_ids and r.selected_option)
        return watched + answered


# ─── HR results serializer ────────────────────────────────────────────────────

class ResultsAssignmentSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    responses        = CandidateResponseSerializer(many=True, read_only=True)
    total_items      = serializers.SerializerMethodField()
    pass_rate        = serializers.SerializerMethodField()

    class Meta:
        model  = CandidateAssignment
        fields = [
            'id', 'assessment_title', 'status',
            'score', 'max_score', 'total_items', 'pass_rate',
            'completed_at', 'responses',
        ]

    def get_total_items(self, obj: CandidateAssignment) -> int:
        return obj.assessment.items.count()

    def get_pass_rate(self, obj: CandidateAssignment) -> str:
        if obj.max_score == 0:
            return 'N/A'
        pct = round((obj.score / obj.max_score) * 100)
        return f'{pct}%'


# ─── HR: per-assessment candidate participation list ─────────────────────────

class AssessmentCandidateSerializer(serializers.ModelSerializer):
    candidate_id   = serializers.IntegerField(source='candidate.id',    read_only=True)
    candidate_name = serializers.CharField(source='candidate.name',     read_only=True)
    candidate_email = serializers.CharField(source='candidate.email',   read_only=True)
    pass_score     = serializers.IntegerField(source='max_score',       read_only=True)
    score_awarded  = serializers.IntegerField(source='score',           read_only=True)
    pass_percentage = serializers.SerializerMethodField()

    class Meta:
        model  = CandidateAssignment
        fields = [
            'id',
            'candidate_id', 'candidate_name', 'candidate_email',
            'status',
            'attempt_count',
            'pass_score', 'score_awarded', 'pass_percentage',
            'completed_at', 'created_at',
        ]

    def get_pass_percentage(self, obj: CandidateAssignment) -> str:
        if obj.max_score == 0:
            return 'N/A'
        pct = round((obj.score / obj.max_score) * 100)
        return f'{pct}%'
