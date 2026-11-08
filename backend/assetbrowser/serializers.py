from rest_framework import serializers

from .models import AssetSnapshot


class AssetRefSerializer(serializers.Serializer):
    space_id = serializers.CharField(max_length=128)
    path = serializers.CharField(max_length=2048)


class AddAssetsSerializer(serializers.Serializer):
    items = AssetRefSerializer(many=True, allow_empty=False)
    destination_folder_id = serializers.CharField(required=False, allow_null=True)


class AssetSnapshotSerializer(serializers.ModelSerializer):
    added_at = serializers.DateTimeField(source='created_at', read_only=True)
    added_by = serializers.EmailField(source='added_by.email', read_only=True, default=None)
    dataroom_document_id = serializers.CharField(read_only=True)

    class Meta:
        model = AssetSnapshot
        fields = [
            'id', 'status', 'error', 'source_space_name', 'source_path', 'source_md5', 'sha256',
            'file_size', 'reused_document', 'added_at', 'added_by', 'dataroom_document_id',
        ]
