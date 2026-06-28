# replication/cloud/storage.py – Multi‑cloud storage adapter
import os
import io
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, BinaryIO
import hashlib

class CloudStorageBackend(ABC):
    @abstractmethod
    def upload(self, key: str, data: bytes, metadata: Dict = None) -> bool:
        pass
    @abstractmethod
    def download(self, key: str) -> Optional[bytes]:
        pass
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    @abstractmethod
    def list_keys(self, prefix: str = "") -> list:
        pass

class S3Storage(CloudStorageBackend):
    def __init__(self, bucket: str, region: str = "us-east-1", access_key: str = None, secret_key: str = None):
        self.bucket = bucket
        self.region = region
        self.access_key = access_key or os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self._client = None
    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client('s3', region_name=self.region, aws_access_key_id=self.access_key, aws_secret_access_key=self.secret_key)
        return self._client
    def upload(self, key: str, data: bytes, metadata: Dict = None) -> bool:
        try:
            self._get_client().put_object(Bucket=self.bucket, Key=key, Body=data, Metadata=metadata or {})
            return True
        except Exception as e:
            print(f"S3 upload error: {e}")
            return False
    def download(self, key: str) -> Optional[bytes]:
        try:
            resp = self._get_client().get_object(Bucket=self.bucket, Key=key)
            return resp['Body'].read()
        except:
            return None
    def delete(self, key: str) -> bool:
        try:
            self._get_client().delete_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False
    def list_keys(self, prefix: str = "") -> list:
        try:
            resp = self._get_client().list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            return [obj['Key'] for obj in resp.get('Contents', [])]
        except:
            return []

class AzureStorage(CloudStorageBackend):
    def __init__(self, connection_string: str, container: str):
        self.container = container
        self.connection_string = connection_string
        self._client = None
    def _get_client(self):
        if self._client is None:
            from azure.storage.blob import BlobServiceClient
            self._client = BlobServiceClient.from_connection_string(self.connection_string)
        return self._client
    def upload(self, key: str, data: bytes, metadata: Dict = None) -> bool:
        try:
            blob_client = self._get_client().get_blob_client(container=self.container, blob=key)
            blob_client.upload_blob(data, overwrite=True, metadata=metadata)
            return True
        except:
            return False
    def download(self, key: str) -> Optional[bytes]:
        try:
            blob_client = self._get_client().get_blob_client(container=self.container, blob=key)
            return blob_client.download_blob().readall()
        except:
            return None
    def delete(self, key: str) -> bool:
        try:
            blob_client = self._get_client().get_blob_client(container=self.container, blob=key)
            blob_client.delete_blob()
            return True
        except:
            return False
    def list_keys(self, prefix: str = "") -> list:
        try:
            container = self._get_client().get_container_client(self.container)
            blobs = container.list_blobs(name_starts_with=prefix)
            return [b.name for b in blobs]
        except:
            return []

class GCSStorage(CloudStorageBackend):
    def __init__(self, bucket: str, key_file: str = None):
        self.bucket = bucket
        self.key_file = key_file or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        self._client = None
    def _get_client(self):
        if self._client is None:
            from google.cloud import storage
            self._client = storage.Client.from_service_account_json(self.key_file) if self.key_file else storage.Client()
        return self._client
    def upload(self, key: str, data: bytes, metadata: Dict = None) -> bool:
        try:
            bucket = self._get_client().bucket(self.bucket)
            blob = bucket.blob(key)
            blob.upload_from_string(data, content_type="application/octet-stream")
            if metadata:
                blob.metadata = metadata
                blob.patch()
            return True
        except:
            return False
    def download(self, key: str) -> Optional[bytes]:
        try:
            bucket = self._get_client().bucket(self.bucket)
            blob = bucket.blob(key)
            return blob.download_as_bytes()
        except:
            return None
    def delete(self, key: str) -> bool:
        try:
            bucket = self._get_client().bucket(self.bucket)
            blob = bucket.blob(key)
            blob.delete()
            return True
        except:
            return False
    def list_keys(self, prefix: str = "") -> list:
        try:
            bucket = self._get_client().bucket(self.bucket)
            blobs = bucket.list_blobs(prefix=prefix)
            return [b.name for b in blobs]
        except:
            return []

def get_storage(provider: str, config: Dict) -> CloudStorageBackend:
    if provider == "aws":
        return S3Storage(config["bucket"], config.get("region", "us-east-1"), config.get("access_key"), config.get("secret_key"))
    elif provider == "azure":
        return AzureStorage(config["connection_string"], config["container"])
    elif provider == "gcp":
        return GCSStorage(config["bucket"], config.get("key_file"))
    else:
        raise ValueError(f"Unknown provider: {provider}")

# Global storage instance (set on init)
_storage = None
def get_storage():
    global _storage
    if _storage is None:
        # Default from env
        provider = os.environ.get("REPLICATION_PROVIDER", "none")
        if provider == "aws":
            _storage = S3Storage(os.environ.get("S3_BUCKET", "crownstar-replication"))
        elif provider == "azure":
            _storage = AzureStorage(os.environ.get("AZURE_CONNECTION_STRING", ""), os.environ.get("AZURE_CONTAINER", "crownstar"))
        elif provider == "gcp":
            _storage = GCSStorage(os.environ.get("GCS_BUCKET", "crownstar-replication"))
    return _storage
