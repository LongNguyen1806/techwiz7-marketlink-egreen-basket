from rest_framework import serializers


class ClosureSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    start_date = serializers.DateField(read_only=True)
    end_date = serializers.DateField(read_only=True)
    reason = serializers.CharField(read_only=True, allow_null=True)
