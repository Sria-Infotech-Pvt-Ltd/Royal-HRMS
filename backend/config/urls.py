from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.accounts.urls')),
    path('api/branch/', include('apps.branch.urls')),
    path('api/announcements/', include('apps.announcements.urls')),
    path('api/recruitment/',   include('apps.recruitment.urls')),
    path('api/',          include('apps.hrms.urls')),
    path('api/attendance/',    include('apps.attendance.urls')),
    path('api/assessments/',   include('apps.assessments.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/dashboard/',     include('apps.dashboard.urls')),
    path('api/voice/',         include('apps.voice_commands.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

