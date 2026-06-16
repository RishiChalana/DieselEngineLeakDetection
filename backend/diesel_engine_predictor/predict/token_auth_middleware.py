"""
Django Channels middleware that authenticates WebSocket connections via
a DRF token passed as the ?token=<key> query parameter.

Browser WebSocket API cannot send the Authorization header during the
HTTP upgrade handshake, so the token must travel in the URL.  This
middleware reads it, resolves the user from rest_framework.authtoken,
and writes scope["user"] — exactly what EngineConsumer.connect() checks.

Placement: INSIDE AuthMiddlewareStack so this runs AFTER the session
middleware has set scope["user"] (to AnonymousUser when no cookie is
present) and can then override it with the token-authenticated user:

    AuthMiddlewareStack(
        TokenAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    )
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _token_to_user(token_key: str):
    from rest_framework.authtoken.models import Token
    try:
        token = Token.objects.select_related("user").get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()


class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "websocket":
            qs = scope.get("query_string", b"")
            if isinstance(qs, bytes):
                qs = qs.decode()
            keys = parse_qs(qs).get("token", [])
            if keys:
                scope["user"] = await _token_to_user(keys[0])
        return await self.inner(scope, receive, send)
