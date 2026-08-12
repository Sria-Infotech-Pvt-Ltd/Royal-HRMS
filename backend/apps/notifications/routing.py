from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    # Catch-all: rejects any other path cleanly instead of Channels raising an
    # unhandled ValueError (and dumping a traceback) for every unmatched connection.
    re_path(r'^.*$', consumers.NotFoundConsumer.as_asgi()),
]
