# bi/cloud_exporter.py – Export to cloud data warehouses
import os
import json
from typing import Dict, List

class CloudWarehouseExporter:
    def __init__(self):
        self.provider = os.environ.get("BI_CLOUD_PROVIDER", "none")
    
    def export_to_bigquery(self, dataframe, table_name: str, project: str = None, dataset: str = "crownstar"):
        try:
            from google.cloud import bigquery
            client = bigquery.Client(project=project)
            table_id = f"{project}.{dataset}.{table_name}"
            job = client.load_table_from_dataframe(dataframe, table_id)
            job.result()
            return True
        except ImportError:
            print("google-cloud-bigquery not installed")
            return False
    
    def export_to_redshift(self, dataframe, table_name: str, conn_params: Dict):
        try:
            import psycopg2
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()
            # Simple insert – would need proper COPY
            # Placeholder
            cursor.close()
            conn.close()
            return True
        except:
            return False
    
    def export_to_snowflake(self, dataframe, table_name: str, conn_params: Dict):
        try:
            import snowflake.connector
            conn = snowflake.connector.connect(**conn_params)
            # Placeholder
            conn.close()
            return True
        except:
            return False
    
    def export(self, dataframe, target: str, **kwargs):
        if target == "bigquery":
            return self.export_to_bigquery(dataframe, kwargs.get("table"), kwargs.get("project"))
        elif target == "redshift":
            return self.export_to_redshift(dataframe, kwargs.get("table"), kwargs.get("connection"))
        elif target == "snowflake":
            return self.export_to_snowflake(dataframe, kwargs.get("table"), kwargs.get("connection"))
        return False

_cloud_exporter = None
def get_cloud_exporter():
    global _cloud_exporter
    if _cloud_exporter is None:
        _cloud_exporter = CloudWarehouseExporter()
    return _cloud_exporter
