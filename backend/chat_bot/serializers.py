from rest_framework import serializers

MAX_MESSAGES = 10
MAX_MESSAGE_CHARS = 1000


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(max_length=MAX_MESSAGE_CHARS, trim_whitespace=True)


class ChatRequestSerializer(serializers.Serializer):
    """CH-01 body: the recent conversation, oldest first, ending with the user's message."""

    messages = ChatMessageSerializer(many=True, allow_empty=False, max_length=MAX_MESSAGES)

    def validate_messages(self, messages):
        if messages[-1]["role"] != "user":
            raise serializers.ValidationError("The last message must be the user's.")
        return messages
