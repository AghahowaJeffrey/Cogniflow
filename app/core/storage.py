import aioboto3
from typing import BinaryIO, Optional
from app.core.config import settings

class StorageService:
    def __init__(self):
        self.session = aioboto3.Session()
        self.endpoint_url = f"http://{settings.MINIO_ENDPOINT}"
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.bucket_name = settings.S3_BUCKET

    async def upload_file(self, file_data: bytes, file_key: str, content_type: str) -> bool:
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            await s3.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_data,
                ContentType=content_type,
            )
            return True

    async def get_file(self, file_key: str) -> bytes:
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            response = await s3.get_object(Bucket=self.bucket_name, Key=file_key)
            async with response["Body"] as stream:
                return await stream.read()

storage_service = StorageService()
