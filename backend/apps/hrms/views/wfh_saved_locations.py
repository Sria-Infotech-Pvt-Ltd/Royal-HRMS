from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from core.responses import error, first_error, success

from ..models import WFHSavedLocation
from ..serializers import WFHSavedLocationSerializer


class WFHSavedLocationListCreateView(APIView):
    """
    GET  /wfh/saved-locations/  — the current employee's own saved WFH
         locations, so the request form can offer a dropdown instead of
         re-capturing GPS coordinates every time.
    POST /wfh/saved-locations/  — save a new one.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        locations = WFHSavedLocation.objects.filter(employee=request.user)
        return success(
            'Saved locations retrieved.',
            WFHSavedLocationSerializer(locations, many=True).data,
        )

    def post(self, request):
        serializer = WFHSavedLocationSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        if WFHSavedLocation.objects.filter(employee=request.user, label__iexact=serializer.validated_data['label']).exists():
            return error('You already have a saved location with this label.')
        location = serializer.save(employee=request.user)
        return success(
            'Location saved.',
            WFHSavedLocationSerializer(location).data,
            http_status=status.HTTP_201_CREATED,
        )


class WFHSavedLocationDetailView(APIView):
    """DELETE /wfh/saved-locations/<id>/ — remove one of the employee's own saved locations."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, location_id):
        location = WFHSavedLocation.objects.filter(id=location_id, employee=request.user).first()
        if not location:
            return error('Saved location not found.', http_status=status.HTTP_404_NOT_FOUND)
        location.delete()
        return success('Saved location removed.')
