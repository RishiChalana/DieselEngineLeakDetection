from django.urls import re_path
from .consumer import EngineConsumer

websocket_urlpatterns = [
    re_path(r"ws/engine/$", EngineConsumer.as_asgi()),
]