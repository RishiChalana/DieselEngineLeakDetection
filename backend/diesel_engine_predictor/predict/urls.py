from django.contrib import admin
from django.urls import path
from django.urls import include
from .views import Predict
urlpatterns = [
    path('predict',Predict.as_view(),name='predict'),
]