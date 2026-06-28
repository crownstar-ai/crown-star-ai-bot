# analytics/report_generator.py – Generate usage reports
import csv
import json
from io import StringIO
from datetime import datetime
from typing import Dict, List
import os
from pathlib import Path

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

class ReportGenerator:
    def __init__(self, analytics_service):
        self.analytics = analytics_service
    
    def generate_csv(self, start_date: str, end_date: str) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'User ID', 'Tier', 'Model', 'Input Chars', 'Output Chars', 'Latency ms', 'Cost'])
        cursor = self.analytics.conn.cursor()
        cursor.execute('''
            SELECT timestamp, user_id, tier, model, input_chars, output_chars, latency_ms, cost
            FROM requests
            WHERE date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp
        ''', (start_date, end_date))
        for row in cursor.fetchall():
            writer.writerow(row)
        return output.getvalue()
    
    def generate_json(self, start_date: str, end_date: str) -> str:
        cursor = self.analytics.conn.cursor()
        cursor.execute('''
            SELECT timestamp, user_id, tier, model, input_chars, output_chars, latency_ms, cost, modules_active
            FROM requests
            WHERE date(timestamp) BETWEEN ? AND ?
        ''', (start_date, end_date))
        rows = cursor.fetchall()
        data = [{
            'timestamp': r[0], 'user_id': r[1], 'tier': r[2], 'model': r[3],
            'input_chars': r[4], 'output_chars': r[5], 'latency_ms': r[6],
            'cost': r[7], 'modules_active': json.loads(r[8]) if r[8] else []
        } for r in rows]
        return json.dumps(data, indent=2)
    
    def generate_html_summary(self, start_date: str, end_date: str) -> str:
        summary = self.analytics.get_usage_summary(start_date, end_date)
        by_tier = self.analytics.get_usage_by_tier(start_date, end_date)
        by_model = self.analytics.get_usage_by_model(start_date, end_date)
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head><title>CrownStar Usage Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #ffcc4d; }}
            .summary {{ background: #f5f5f5; padding: 20px; border-radius: 10px; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #ffcc4d; }}
        </style>
        </head>
        <body>
        <h1>⭐ CrownStar Usage Report</h1>
        <p>Period: {start_date} to {end_date}</p>
        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Total Requests:</strong> {summary['total_requests']}</p>
            <p><strong>Total Input Characters:</strong> {summary['total_input_chars']:,}</p>
            <p><strong>Total Output Characters:</strong> {summary['total_output_chars']:,}</p>
            <p><strong>Total Cost:</strong> ${summary['total_cost']:.4f}</p>
            <p><strong>Unique Users:</strong> {summary['unique_users']}</p>
            <p><strong>Average Latency:</strong> {summary['avg_latency_ms']:.1f} ms</p>
        </div>
        <h2>Usage by Tier</h2>
        <table>
            <tr><th>Tier</th><th>Requests</th><th>Cost</th><th>Characters</th></tr>
        '''
        for tier, data in by_tier.items():
            html += f'<tr><td>{tier}</td><td>{data["requests"]}</td><td>${data["cost"]:.4f}</td><td>{data["characters"]:,}</td></tr>'
        html += '</table><h2>Usage by Model</h2><table><tr><th>Model</th><th>Requests</th><th>Cost</th><th>Avg Latency (ms)</th></tr>'
        for model, data in by_model.items():
            html += f'<tr><td>{model}</td><td>{data["requests"]}</td><td>${data["cost"]:.4f}</td><td>{data["avg_latency_ms"]:.1f}</td></tr>'
        html += '</table></body></html>'
        return html
    
    def generate_pdf(self, start_date: str, end_date: str, output_path: str):
        if not HAS_WEASYPRINT:
            raise RuntimeError("WeasyPrint not installed. Install with: pip install weasyprint")
        html = self.generate_html_summary(start_date, end_date)
        HTML(string=html).write_pdf(output_path)
        return output_path
