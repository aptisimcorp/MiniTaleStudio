import urllib3
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from app.config import settings

# Suppress InsecureRequestWarning for Cosmos DB Emulator self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONTAINERS = {
    "configurations": "/category",
    "schedules": "/schedule_type",
    "jobs": "/status",
    "users": "/role",
    "videos": "/category",
    "youtube_accounts": "/user_id",
}


def _is_emulator(connection_string: str) -> bool:
    return "localhost" in connection_string or "127.0.0.1" in connection_string


class CosmosDB:
    def __init__(self):
        self.client = None
        self.database = None
        self.containers = {}

    def connect(self):
        if not settings.cosmos_db_connection_string:
            print("[CosmosDB] No connection string configured - running in offline mode.")
            return

        try:
            conn_str = settings.cosmos_db_connection_string

            # Cosmos DB Emulator uses a self-signed cert; disable TLS verification
            if _is_emulator(conn_str):
                self.client = CosmosClient.from_connection_string(
                    conn_str,
                    connection_verify=False,
                )
                print("[CosmosDB] Using Cosmos DB Emulator (SSL verification disabled).")
            else:
                self.client = CosmosClient.from_connection_string(conn_str)

            self.database = self.client.create_database_if_not_exists(id=settings.cosmos_db_database_name)

            for name, partition_key_path in CONTAINERS.items():
                self.containers[name] = self.database.create_container_if_not_exists(
                    id=name,
                    partition_key=PartitionKey(path=partition_key_path),
                )
            print("[CosmosDB] Connected successfully.")
        except exceptions.CosmosHttpResponseError as e:
            print(f"[CosmosDB] Connection error: {e.message}")

    def get_container(self, name: str):
        return self.containers.get(name)

    # ---- Generic CRUD helpers ----

    def create_item(self, container_name: str, item: dict) -> dict:
        container = self.get_container(container_name)
        if container is None:
            return item  # offline fallback
        return container.create_item(body=item)

    def read_item(self, container_name: str, item_id: str, partition_key: str) -> dict | None:
        container = self.get_container(container_name)
        if container is None:
            return None
        try:
            return container.read_item(item=item_id, partition_key=partition_key)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def query_items(self, container_name: str, query: str, parameters: list | None = None) -> list:
        container = self.get_container(container_name)
        if container is None:
            return []
        return list(
            container.query_items(query=query, parameters=parameters or [], enable_cross_partition_query=True)
        )

    def upsert_item(self, container_name: str, item: dict) -> dict:
        container = self.get_container(container_name)
        if container is None:
            return item
        return container.upsert_item(body=item)

    def delete_item(self, container_name: str, item_id: str, partition_key: str) -> None:
        container = self.get_container(container_name)
        if container is None:
            return
        try:
            container.delete_item(item=item_id, partition_key=partition_key)
        except exceptions.CosmosResourceNotFoundError:
            pass


cosmos_db = CosmosDB()
