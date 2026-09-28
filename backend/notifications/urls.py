from django.urls import path

from notifications.views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications-list"),
    path("unread-count/", NotificationUnreadCountView.as_view(), name="notifications-unread-count"),
    path("read-all/", NotificationMarkAllReadView.as_view(), name="notifications-read-all"),
    path("<int:notification_id>/read/", NotificationMarkReadView.as_view(), name="notifications-read"),
]
