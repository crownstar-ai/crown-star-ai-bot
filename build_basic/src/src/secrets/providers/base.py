# secrets/providers/base.py – Abstract interface for secret stores
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

@dataclass
class SecretMetadata:
    key: str
    version: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict = None

class SecretProvider(ABC):
    @abstractmethod
    def get(self, key: str, version: str = "latest") -> Optional[str]:
        pass
    @abstractmethod
    def set(self, key: str, value: str, metadata: Dict = None) -> bool:
        pass
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        pass
    @abstractmethod
    def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        pass
    @abstractmethod
    def rotate(self, key: str, new_value: str = None) -> Optional[str]:
        """Generate new value if None, store as new version"""
        pass

class LocalFileProvider(SecretProvider):
    """Fallback: encrypted local file storage (AES-256)"""
    def __init__(self, storage_dir: str = "data/secrets", encryption_key: bytes = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.encryption_key = encryption_key or b"crownstar-secrets-key-32bytes-long!!"
        self._cache = {}
    def _encrypt(self, data: str) -> str:
        from cryptography.fernet import Fernet
        f = Fernet(self.encryption_key)
        return f.encrypt(data.encode()).decode()
    def _decrypt(self, encrypted: str) -> str:
        from cryptography.fernet import Fernet
        f = Fernet(self.encryption_key)
        return f.decrypt(encrypted.encode()).decode()
    def _get_path(self, key: str) -> Path:
        import hashlib
        safe = hashlib.md5(key.encode()).hexdigest()
        return self.storage_dir / f"{safe}.enc"
    def get(self, key: str, version: str = "latest") -> Optional[str]:
        path = self._get_path(key)
        if not path.exists():
            return None
        with open(path, "r") as f:
            encrypted = f.read()
        return self._decrypt(encrypted)
    def set(self, key: str, value: str, metadata: Dict = None) -> bool:
        path = self._get_path(key)
        encrypted = self._encrypt(value)
        with open(path, "w") as f:
            f.write(encrypted)
        return True
    def delete(self, key: str) -> bool:
        path = self._get_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    def list_keys(self, prefix: str = "") -> List[str]:
        import hashlib
        # Cannot list easily; store index file
        index_file = self.storage_dir / "index.json"
        if index_file.exists():
            with open(index_file, "r") as f:
                index = json.load(f)
                return [k for k in index if k.startswith(prefix)]
        return []
    def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        # Not implemented for local
        return None
    def rotate(self, key: str, new_value: str = None) -> Optional[str]:
        import secrets
        if new_value is None:
            new_value = secrets.token_urlsafe(32)
        if self.set(key, new_value):
            return new_value
        return None

class HashiCorpVaultProvider(SecretProvider):
    def __init__(self, url: str = "http://localhost:8200", token: str = None, mount_point: str = "secret"):
        self.url = url.rstrip('/')
        self.token = token
        self.mount_point = mount_point
        self._headers = {"X-Vault-Token": token} if token else {}
    def _request(self, method: str, path: str, data: dict = None):
        import requests
        url = f"{self.url}/v1/{path}"
        resp = requests.request(method, url, headers=self._headers, json=data)
        resp.raise_for_status()
        return resp.json()
    def get(self, key: str, version: str = "latest") -> Optional[str]:
        try:
            data = self._request("GET", f"{self.mount_point}/data/{key}")
            return data["data"]["data"].get("value")
        except:
            return None
    def set(self, key: str, value: str, metadata: Dict = None) -> bool:
        payload = {"data": {"value": value}}
        if metadata:
            payload["options"] = metadata
        self._request("POST", f"{self.mount_point}/data/{key}", payload)
        return True
    def delete(self, key: str) -> bool:
        self._request("DELETE", f"{self.mount_point}/metadata/{key}")
        return True
    def list_keys(self, prefix: str = "") -> List[str]:
        try:
            data = self._request("LIST", f"{self.mount_point}/metadata/{prefix}")
            return data["data"]["keys"]
        except:
            return []
    def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        try:
            data = self._request("GET", f"{self.mount_point}/metadata/{key}")
            meta = data["data"]
            return SecretMetadata(
                key=key,
                version=str(meta.get("current_version", 1)),
                created_at=datetime.fromisoformat(meta["created_time"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(meta["updated_time"].replace('Z', '+00:00')),
                metadata=meta
            )
        except:
            return None
    def rotate(self, key: str, new_value: str = None) -> Optional[str]:
        if new_value is None:
            import secrets
            new_value = secrets.token_urlsafe(32)
        if self.set(key, new_value):
            return new_value
        return None

class AWSSecretsManagerProvider(SecretProvider):
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self._client = None
    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client('secretsmanager', region_name=self.region)
        return self._client
    def get(self, key: str, version: str = "latest") -> Optional[str]:
        try:
            resp = self._get_client().get_secret_value(SecretId=key, VersionStage=version if version!="latest" else "AWSCURRENT")
            return resp.get("SecretString")
        except:
            return None
    def set(self, key: str, value: str, metadata: Dict = None) -> bool:
        try:
            self._get_client().create_secret(Name=key, SecretString=value)
        except:
            self._get_client().put_secret_value(SecretId=key, SecretString=value)
        return True
    def delete(self, key: str) -> bool:
        self._get_client().delete_secret(SecretId=key, ForceDeleteWithoutRecovery=True)
        return True
    def list_keys(self, prefix: str = "") -> List[str]:
        resp = self._get_client().list_secrets()
        return [s["Name"] for s in resp.get("SecretList", []) if s["Name"].startswith(prefix)]
    def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        try:
            resp = self._get_client().describe_secret(SecretId=key)
            return SecretMetadata(
                key=key,
                version=resp.get("VersionIdsToStages", {}).get("AWSCURRENT", ["1"])[0],
                created_at=resp["CreatedDate"],
                updated_at=resp.get("LastChangedDate", resp["CreatedDate"]),
                metadata=resp
            )
        except:
            return None
    def rotate(self, key: str, new_value: str = None) -> Optional[str]:
        # Stub – would use rotation lambda
        if new_value is None:
            import secrets
            new_value = secrets.token_urlsafe(32)
        self.set(key, new_value)
        return new_value

class AzureKeyVaultProvider(SecretProvider):
    def __init__(self, vault_url: str, credential=None):
        self.vault_url = vault_url
        self.credential = credential
        self._client = None
    def _get_client(self):
        if self._client is None:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            cred = self.credential or DefaultAzureCredential()
            self._client = SecretClient(vault_url=self.vault_url, credential=cred)
        return self._client
    def get(self, key: str, version: str = "latest") -> Optional[str]:
        try:
            secret = self._get_client().get_secret(key, version=version if version!="latest" else "")
            return secret.value
        except:
            return None
    def set(self, key: str, value: str, metadata: Dict = None) -> bool:
        self._get_client().set_secret(key, value)
        return True
    def delete(self, key: str) -> bool:
        poller = self._get_client().begin_delete_secret(key)
        poller.result()
        return True
    def list_keys(self, prefix: str = "") -> List[str]:
        items = self._get_client().list_properties_of_secrets()
        return [s.name for s in items if s.name.startswith(prefix)]
    def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        try:
            secret = self._get_client().get_secret(key)
            return SecretMetadata(
                key=key,
                version=secret.properties.version,
                created_at=secret.properties.created_on,
                updated_at=secret.properties.updated_on,
                metadata={"enabled": secret.properties.enabled}
            )
        except:
            return None
    def rotate(self, key: str, new_value: str = None) -> Optional[str]:
        if new_value is None:
            import secrets
            new_value = secrets.token_urlsafe(32)
        self.set(key, new_value)
        return new_value

class GCPSecretManagerProvider(SecretProvider):
    def __init__(self, project_id: str):
        self.project_id = project_id
        self._client = None
    def _get_client(self):
        if self._client is None:
            from google.cloud import secretmanager
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client
    def _secret_path(self, key: str) -> str:
        return f"projects/{self.project_id}/secrets/{key}"
    def get(self, key: str, version: str = "latest") -> Optional[str]:
        try:
            if version == "latest":
                version = "latest"
            name = f"{self._secret_path(key)}/versions/{version}"
            resp = self._get_client().access_secret_version(request={"name": name})
            return resp.payload.data.decode('utf-8')
        except:
            return None
    def set(self, key: str, value: str, metadata: Dict = None) -> bool:
        parent = f"projects/{self.project_id}"
        try:
            self._get_client().create_secret(request={"parent": parent, "secret_id": key, "secret": {}})
        except:
            pass
        payload = value.encode('utf-8')
        self._get_client().add_secret_version(request={"parent": self._secret_path(key), "payload": {"data": payload}})
        return True
    def delete(self, key: str) -> bool:
        self._get_client().delete_secret(request={"name": self._secret_path(key)})
        return True
    def list_keys(self, prefix: str = "") -> List[str]:
        parent = f"projects/{self.project_id}"
        resp = self._get_client().list_secrets(request={"parent": parent})
        return [s.name.split('/')[-1] for s in resp if s.name.split('/')[-1].startswith(prefix)]
    def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        try:
            secret = self._get_client().get_secret(request={"name": self._secret_path(key)})
            return SecretMetadata(
                key=key,
                version="latest",
                created_at=secret.create_time,
                updated_at=secret.create_time,
                metadata={"labels": secret.labels}
            )
        except:
            return None
    def rotate(self, key: str, new_value: str = None) -> Optional[str]:
        if new_value is None:
            import secrets
            new_value = secrets.token_urlsafe(32)
        self.set(key, new_value)
        return new_value

def get_provider(provider_name: str, config: dict) -> SecretProvider:
    if provider_name == "hashicorp_vault":
        return HashiCorpVaultProvider(
            config.get("url", "http://localhost:8200"),
            config.get("token"),
            config.get("mount_point", "secret")
        )
    elif provider_name == "aws":
        return AWSSecretsManagerProvider(config.get("region", "us-east-1"))
    elif provider_name == "azure":
        return AzureKeyVaultProvider(config.get("vault_url"), config.get("credential"))
    elif provider_name == "gcp":
        return GCPSecretManagerProvider(config.get("project_id"))
    else:
        return LocalFileProvider()
