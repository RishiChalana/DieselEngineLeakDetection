"""URL routing for the session_analysis app."""
from django.urls import path

from .views import AnalyzeSessionView

urlpatterns = [
    path("session/", AnalyzeSessionView.as_view(), name="session_analysis"),
]
