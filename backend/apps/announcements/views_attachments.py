"""Authorised download of an announcement attachment.

A file is handed out only to (a) a signed-in person who may see that announcement (same audience rule as the Announcements page),
or (b) someone holding a valid, unexpired signed token for exactly that attachment (the link in the announcement e-mail). Either
way the response is a redirect to a short-lived signed storage URL; the permanent storage address is never exposed.
"""
from __future__ import annotations

from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.announcements.models import AnnouncementAttachment
from apps.announcements.services_announcements_visibility import visible_announcements
from apps.announcements.services_attachments import download_token_is_valid, signed_download_url
from core.responses import error


class AnnouncementAttachmentDownloadView(APIView):
    # Open at the door on purpose: who may download is decided in get(), because an e-mail recipient may not be signed in.
    permission_classes = [AllowAny]

    def get(self, request, pk: int, attachment_id):
        attachment = AnnouncementAttachment.objects.filter(pk=attachment_id, announcement_id=pk).first()
        if attachment is None:
            return error('Attachment not found.', http_status=status.HTTP_404_NOT_FOUND)

        token = request.query_params.get('token', '')
        has_valid_token = bool(token) and download_token_is_valid(token, pk, attachment.pk)
        user = request.user
        signed_in = bool(user and user.is_authenticated)
        may_see = signed_in and visible_announcements(user).filter(pk=pk).exists()

        if not (may_see or has_valid_token):
            if token:
                return error('This download link is invalid or has expired.', http_status=status.HTTP_403_FORBIDDEN)
            if not signed_in:
                return error('Sign in to download this file.', http_status=status.HTTP_401_UNAUTHORIZED)
            # Signed in but not in the audience: say nothing about whether the file exists.
            return error('Attachment not found.', http_status=status.HTTP_404_NOT_FOUND)

        response = HttpResponseRedirect(signed_download_url(attachment))
        response['Cache-Control'] = 'no-store'
        return response
