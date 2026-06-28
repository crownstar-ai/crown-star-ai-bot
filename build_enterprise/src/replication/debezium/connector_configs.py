# replication/debezium/connector_configs.py – Predefined Debezium connector configurations
import json
from typing import Dict

class DebeziumConnectorBuilder:
    @staticmethod
    def postgresql(server_name: str, host: str, port: int, database: str, user: str, password: str, 
                   table_include_list: str = None, slot_name: str = None) -> Dict:
        config = {
            "name": f"debezium-postgres-{server_name}",
            "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
            "database.hostname": host,
            "database.port": str(port),
            "database.dbname": database,
            "database.user": user,
            "database.password": password,
            "database.server.name": server_name,
            "plugin.name": "pgoutput",
            "slot.name": slot_name or f"debezium_{server_name}",
            "publication.name": f"dbz_publication_{server_name}",
            "publication.autocreate.mode": "filtered",
            "tombstones.on.delete": "false",
            "key.converter": "org.apache.kafka.connect.json.JsonConverter",
            "value.converter": "org.apache.kafka.connect.json.JsonConverter",
            "key.converter.schemas.enable": "false",
            "value.converter.schemas.enable": "false",
            "transforms": "unwrap",
            "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
            "transforms.unwrap.drop.tombstones": "true"
        }
        if table_include_list:
            config["table.include.list"] = table_include_list
        return config
    
    @staticmethod
    def mysql(server_name: str, host: str, port: int, database: str, user: str, password: str,
              table_include_list: str = None) -> Dict:
        config = {
            "name": f"debezium-mysql-{server_name}",
            "connector.class": "io.debezium.connector.mysql.MySqlConnector",
            "database.hostname": host,
            "database.port": str(port),
            "database.dbname": database,
            "database.user": user,
            "database.password": password,
            "database.server.name": server_name,
            "database.history.kafka.bootstrap.servers": "kafka:9092",
            "database.history.kafka.topic": f"schema-changes.{server_name}",
            "tombstones.on.delete": "false",
            "key.converter": "org.apache.kafka.connect.json.JsonConverter",
            "value.converter": "org.apache.kafka.connect.json.JsonConverter",
            "key.converter.schemas.enable": "false",
            "value.converter.schemas.enable": "false",
            "transforms": "unwrap",
            "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
            "transforms.unwrap.drop.tombstones": "true"
        }
        if table_include_list:
            config["table.include.list"] = table_include_list
        return config
    
    @staticmethod
    def sqlserver(server_name: str, host: str, port: int, database: str, user: str, password: str,
                  schema_include_list: str = None) -> Dict:
        config = {
            "name": f"debezium-sqlserver-{server_name}",
            "connector.class": "io.debezium.connector.sqlserver.SqlServerConnector",
            "database.hostname": host,
            "database.port": str(port),
            "database.dbname": database,
            "database.user": user,
            "database.password": password,
            "database.server.name": server_name,
            "table.include.list": "dbo.conversations,dbo.users",
            "key.converter": "org.apache.kafka.connect.json.JsonConverter",
            "value.converter": "org.apache.kafka.connect.json.JsonConverter",
            "key.converter.schemas.enable": "false",
            "value.converter.schemas.enable": "false",
            "transforms": "unwrap",
            "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState"
        }
        if schema_include_list:
            config["schema.include.list"] = schema_include_list
        return config
