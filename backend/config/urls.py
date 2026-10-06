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
    path('api/',               include('apps.hrms.urls')),
    path('api/attendance/',    include('apps.attendance.urls')),
    path('api/assessments/',   include('apps.assessments.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/dashboard/',     include('apps.dashboard.urls')),
    path('api/payroll/',       include('apps.payroll.urls')),
    path('api/voice/',         include('apps.voice_commands.urls')),
    path('api/performance/',   include('apps.performance.urls')),
    # New in Phase 1 — this is the only app in the whole backend namespaced
    # under /api/v1/ rather than bare /api/ (every other app's URLs predate
    # any versioning convention). Deliberate: platform_core is a brand new
    # surface, so it starts correctly rather than needing a breaking move
    # later; existing apps are untouched.
    path('api/v1/platform/', include('apps.platform_core.urls')),
]
 
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

 