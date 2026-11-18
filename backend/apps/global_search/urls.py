from django.urls import path

from .views import GlobalSearchView, ModuleSearchView, SearchRegistryView

urlpatterns = [
    path('', GlobalSearchView.as_view(), name='global-search'),
    path('registry/', SearchRegistryView.as_view(), name='global-search-registry'),
    path('<str:module>/', ModuleSearchView.as_view(), name='global-search-module'),
]
