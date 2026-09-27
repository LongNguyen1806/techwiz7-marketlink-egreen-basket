from django.urls import path

from chat_bot.views import ChatMessagesView

app_name = "chat_bot"

urlpatterns = [
    path("messages/", ChatMessagesView.as_view(), name="chat-messages"),
]
