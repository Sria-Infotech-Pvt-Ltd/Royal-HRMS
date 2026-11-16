from django.urls import path

from .views import (
    AnnouncementDetailView,
    AnnouncementListCreateView,
    AnnouncementReactView,
    AnnouncementViewTrackView,
)
from .views_attachments import AnnouncementAttachmentDownloadView

urlpatterns = [
    path('',             AnnouncementListCreateView.as_view(), name='announcement-list-create'),
    path('<int:pk>/',    AnnouncementDetailView.as_view(),     name='announcement-detail'),
    path('<int:pk>/react/', AnnouncementReactView.as_view(),   name='announcement-react'),
    path('<int:pk>/view/',  AnnouncementViewTrackView.as_view(), name='announcement-view'),
    path('<int:pk>/attachments/<uuid:attachment_id>/download/', AnnouncementAttachmentDownloadView.as_view(), name='announcement-attachment-download'),
]
