# bi/service.py – BI data extraction and aggregation
import json
import csv
import io
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .schema import get_warehouse

class BIService:
    def __init__(self):
        self.warehouse = get_warehouse()
    
    def get_usage_report(self, start_date: str, end_date: str, group_by: str = "day") -> pd.DataFrame:
        """Return usage aggregated by time period"""
        query = f'''
            SELECT 
                d.date_id,
                d.year, d.month, d.day,
                SUM(f.request_count) as total_requests,
                SUM(f.input_chars) as total_input_chars,
                SUM(f.output_chars) as total_output_chars,
                SUM(f.total_cost) as total_cost,
                AVG(f.latency_avg_ms) as avg_latency
            FROM fact_usage f
            JOIN dim_date d ON f.date_id = d.date_id
            WHERE f.date_id BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY {group_by}
            ORDER BY f.date_id
        '''
        return pd.read_sql_query(query, self.warehouse.conn)
    
    def get_by_tier(self, start_date: str, end_date: str) -> pd.DataFrame:
        query = f'''
            SELECT 
                t.tier_name,
                SUM(f.request_count) as requests,
                SUM(f.total_cost) as cost,
                SUM(f.input_chars + f.output_chars) as total_chars
            FROM fact_usage f
            JOIN dim_tier t ON f.tier_id = t.tier_id
            WHERE f.date_id BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY t.tier_name
        '''
        return pd.read_sql_query(query, self.warehouse.conn)
    
    def get_by_model(self, start_date: str, end_date: str) -> pd.DataFrame:
        query = f'''
            SELECT 
                m.model_name,
                m.provider,
                SUM(f.request_count) as requests,
                AVG(f.latency_avg_ms) as avg_latency,
                SUM(f.total_cost) as cost
            FROM fact_usage f
            JOIN dim_model m ON f.model_id = m.model_id
            WHERE f.date_id BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY m.model_name, m.provider
        '''
        return pd.read_sql_query(query, self.warehouse.conn)
    
    def export_csv(self, start_date: str, end_date: str, output_path: str) -> str:
        df = self.get_usage_report(start_date, end_date)
        df.to_csv(output_path, index=False)
        return output_path
    
    def export_json(self, start_date: str, end_date: str, output_path: str) -> str:
        df = self.get_usage_report(start_date, end_date)
        df.to_json(output_path, orient="records", date_format="iso")
        return output_path
    
    def export_parquet(self, start_date: str, end_date: str, output_path: str) -> str:
        df = self.get_usage_report(start_date, end_date)
        df.to_parquet(output_path, index=False)
        return output_path
    
    def export_excel(self, start_date: str, end_date: str, output_path: str) -> str:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            self.get_usage_report(start_date, end_date).to_excel(writer, sheet_name="Usage")
            self.get_by_tier(start_date, end_date).to_excel(writer, sheet_name="By Tier")
            self.get_by_model(start_date, end_date).to_excel(writer, sheet_name="By Model")
        return output_path

_bi_service = None
def get_bi_service():
    global _bi_service
    if _bi_service is None:
        _bi_service = BIService()
    return _bi_service
