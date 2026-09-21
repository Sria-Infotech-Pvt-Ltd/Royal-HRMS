from django.urls import path

from .views import (
    AcknowledgeReviewView,
    AppraisalBannerSummaryView,
    CalibrateReviewView,
    HRReviewQueueView,
    ManagerReviewDetailView,
    MyGoalDetailView,
    MyGoalsView,
    MyReviewView,
    PublishReviewView,
    ReviewCycleDetailView,
    ReviewCycleListCreateView,
    SubmitManagerReviewView,
    SubmitMyReviewView,
    TeamReviewListView,
)

urlpatterns = [
    path('cycles/',                ReviewCycleListCreateView.as_view(), name='review-cycle-list'),
    path('cycles/<uuid:pk>/',      ReviewCycleDetailView.as_view(),     name='review-cycle-detail'),

    path('goals/me/',              MyGoalsView.as_view(),               name='my-goals'),
    path('goals/me/<uuid:pk>/',    MyGoalDetailView.as_view(),          name='my-goal-detail'),

    path('reviews/me/',            MyReviewView.as_view(),              name='my-review'),
    path('reviews/me/submit/',     SubmitMyReviewView.as_view(),        name='submit-my-review'),

    path('reviews/team/',                  TeamReviewListView.as_view(),        name='team-review-list'),
    path('reviews/<uuid:pk>/',              ManagerReviewDetailView.as_view(),   name='manager-review-detail'),
    path('reviews/<uuid:pk>/submit/',       SubmitManagerReviewView.as_view(),   name='submit-manager-review'),
    path('reviews/<uuid:pk>/calibrate/',    CalibrateReviewView.as_view(),       name='calibrate-review'),
    path('reviews/<uuid:pk>/publish/',      PublishReviewView.as_view(),         name='publish-review'),
    path('reviews/<uuid:pk>/acknowledge/',  AcknowledgeReviewView.as_view(),     name='acknowledge-review'),

    path('reviews/hr-queue/',      HRReviewQueueView.as_view(),         name='hr-review-queue'),
    path('banner-summary/',        AppraisalBannerSummaryView.as_view(), name='appraisal-banner-summary'),
]
