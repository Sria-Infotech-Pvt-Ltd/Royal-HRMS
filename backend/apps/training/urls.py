from django.urls import path

from apps.training import views as v

urlpatterns = [
    path('courses/', v.CourseListCreateView.as_view(), name='training-courses'),
    path('courses/<uuid:pk>/', v.CourseDetailView.as_view(), name='training-course-detail'),
    path('courses/<uuid:pk>/thumbnail/', v.CourseThumbnailView.as_view(), name='training-course-thumbnail'),
    path('courses/<uuid:pk>/thumbnail/file/', v.CourseThumbnailFileView.as_view(), name='training-course-thumbnail-file'),
    path('courses/<uuid:pk>/materials/', v.MaterialListCreateView.as_view(), name='training-materials'),
    path('courses/<uuid:pk>/materials/reorder/', v.MaterialReorderView.as_view(), name='training-materials-reorder'),
    path('courses/<uuid:pk>/assign/', v.AssignView.as_view(), name='training-assign'),
    path('courses/<uuid:pk>/progress/', v.CourseProgressView.as_view(), name='training-course-progress'),
    path('materials/<uuid:pk>/', v.MaterialDetailView.as_view(), name='training-material-detail'),
    path('materials/<uuid:pk>/file/', v.MaterialFileView.as_view(), name='training-material-file'),
    path('materials/<uuid:pk>/video-source/', v.MaterialVideoSourceView.as_view(), name='training-material-video'),
    path('assignments/<uuid:pk>/', v.AssignmentDeleteView.as_view(), name='training-assignment-delete'),
    path('assignments/<uuid:pk>/reset-assessment/', v.ResetAssessmentView.as_view(), name='training-assignment-reset'),
    path('assessments/', v.AssessmentOptionsView.as_view(), name='training-assessment-options'),
    path('employees/', v.EmployeePickerView.as_view(), name='training-employee-picker'),
    path('dashboard/', v.DashboardView.as_view(), name='training-dashboard'),
    path('reports/', v.ReportView.as_view(), name='training-reports'),
    path('my/', v.MyTrainingListView.as_view(), name='training-my'),
    path('my/<uuid:pk>/', v.MyTrainingDetailView.as_view(), name='training-my-detail'),
    path('my/<uuid:pk>/materials/<uuid:material_id>/<str:action>/', v.MyMaterialActionView.as_view(),
         name='training-my-material'),
    path('my/<uuid:pk>/assessment/<str:action>/', v.MyAssessmentView.as_view(), name='training-my-assessment'),
]
