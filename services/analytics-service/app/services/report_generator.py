# services/analytics-service/app/services/report_generator.py
"""Report generation service"""

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import asyncio
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import pandas as pd
from app.core.config import settings
from app.core.cache import redis_client

class ReportGenerator:
    """Generate analytics reports in various formats"""
    
    def __init__(self):
        self.report_dir = Path(settings.REPORT_STORAGE_PATH)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.tasks = {}
    
    async def generate_async(
        self,
        report_type: str,
        parameters: Dict[str, Any],
        user_id: str
    ) -> str:
        """Generate report asynchronously"""
        task_id = str(uuid.uuid4())
        
        self.tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "result": None
        }
        
        # Start background task
        asyncio.create_task(
            self._generate_report_task(
                task_id, report_type, parameters, user_id
            )
        )
        
        return task_id
    
    async def _generate_report_task(
        self,
        task_id: str,
        report_type: str,
        parameters: Dict[str, Any],
        user_id: str
    ):
        """Background task for report generation"""
        try:
            # Update progress
            self.tasks[task_id]["progress"] = 10
            
            # Generate based on type
            if report_type == "dashboard":
                report_data = await self._generate_dashboard_report(parameters)
            elif report_type == "disease":
                report_data = await self._generate_disease_report(parameters)
            elif report_type == "performance":
                report_data = await self._generate_performance_report(parameters)
            else:
                report_data = await self._generate_export_report(parameters)
            
            self.tasks[task_id]["progress"] = 70
            
            # Generate PDF
            file_path = await self._create_pdf_report(
                report_data, task_id, report_type
            )
            
            self.tasks[task_id]["progress"] = 100
            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["result"] = file_path
            
        except Exception as e:
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["error"] = str(e)
    
    async def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation status"""
        return self.tasks.get(task_id)
    
    async def get_report_file(self, task_id: str) -> Optional[str]:
        """Get generated report file path"""
        task = self.tasks.get(task_id)
        
        if task and task["status"] == "completed":
            return task["result"]
        
        return None
    
    async def list_reports(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        report_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List generated reports"""
        reports = []
        
        for file_path in self.report_dir.glob("*.pdf"):
            stat = file_path.stat()
            reports.append({
                "id": file_path.stem,
                "report_type": "unknown",
                "generated_by": user_id,
                "generated_at": datetime.fromtimestamp(stat.st_mtime),
                "file_size": stat.st_size,
                "format": "pdf",
                "parameters": {}
            })
        
        # Apply filters
        if report_type:
            reports = [r for r in reports if r["report_type"] == report_type]
        
        # Apply pagination
        reports = reports[offset:offset + limit]
        
        return reports
    
    async def delete_report(self, report_id: str) -> bool:
        """Delete a report file"""
        file_path = self.report_dir / f"{report_id}.pdf"
        
        if file_path.exists():
            file_path.unlink()
            return True
        
        return False
    
    async def schedule_report(
        self,
        report_type: str,
        parameters: Dict[str, Any],
        schedule: str,
        recipients: List[str],
        user_id: str
    ) -> Dict[str, Any]:
        """Schedule recurring report generation"""
        schedule_id = str(uuid.uuid4())
        
        # Store schedule in Redis
        schedule_data = {
            "id": schedule_id,
            "report_type": report_type,
            "parameters": parameters,
            "schedule": schedule,
            "recipients": recipients,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "next_run": self._calculate_next_run(schedule)
        }
        
        await redis_client.set(
            f"report_schedule:{schedule_id}",
            schedule_data,
            ttl=30*24*3600  # 30 days
        )
        
        return schedule_data
    
    async def export_data(
        self,
        data: Dict[str, Any],
        format: str
    ) -> Any:
        """Export data in specified format"""
        if format == "csv":
            return await self._export_csv(data)
        elif format == "json":
            return json.dumps(data, default=str)
        elif format == "excel":
            return await self._export_excel(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    async def _generate_dashboard_report(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate dashboard report data"""
        # This would fetch actual analytics data
        return {
            "title": "Dashboard Report",
            "generated_at": datetime.utcnow().isoformat(),
            "data": {
                "summary": {
                    "total_scans": 1250,
                    "total_predictions": 1250,
                    "active_users": 342,
                    "avg_confidence": 0.87
                },
                "top_diseases": [
                    {"disease": "Tomato Early Blight", "count": 450},
                    {"disease": "Maize Rust", "count": 320},
                    {"disease": "Cassava Mosaic", "count": 280}
                ],
                "performance": {
                    "avg_processing_time": 245,
                    "success_rate": 0.94
                }
            }
        }
    
    async def _generate_disease_report(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate disease-focused report"""
        return {
            "title": "Disease Analysis Report",
            "generated_at": datetime.utcnow().isoformat(),
            "diseases": [
                {
                    "name": "Tomato Early Blight",
                    "occurrences": 450,
                    "avg_confidence": 0.89,
                    "severity": "high",
                    "recommendations": [
                        "Apply fungicides",
                        "Remove infected leaves",
                        "Improve air circulation"
                    ]
                }
            ]
        }
    
    async def _generate_performance_report(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate system performance report"""
        return {
            "title": "System Performance Report",
            "generated_at": datetime.utcnow().isoformat(),
            "metrics": {
                "api_response_time": 124,
                "inference_time": 245,
                "success_rate": 0.94,
                "error_rate": 0.02
            }
        }
    
    async def _generate_export_report(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate export data report"""
        return {
            "title": "Data Export",
            "generated_at": datetime.utcnow().isoformat(),
            "data": parameters.get("data", {})
        }
    
    async def _create_pdf_report(
        self,
        report_data: Dict[str, Any],
        task_id: str,
        report_type: str
    ) -> str:
        """Create PDF report from data"""
        file_path = self.report_dir / f"{task_id}.pdf"
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(file_path),
            pagesize=letter,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        
        # Build story
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            alignment=1  # Center
        )
        story.append(Paragraph(report_data['title'], title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Date
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey
        )
        story.append(Paragraph(f"Generated: {report_data['generated_at']}", date_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Add report sections based on type
        if 'summary' in report_data.get('data', {}):
            # Summary table
            summary_data = [[Paragraph("<b>Metric</b>", styles['Normal']),
                           Paragraph("<b>Value</b>", styles['Normal'])]]
            
            for key, value in report_data['data']['summary'].items():
                summary_data.append([
                    Paragraph(key.replace('_', ' ').title(), styles['Normal']),
                    Paragraph(str(value), styles['Normal'])
                ])
            
            table = Table(summary_data, colWidths=[2.5*inch, 2.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(table)
        
        # Build PDF
        doc.build(story)
        
        return str(file_path)
    
    async def _export_csv(self, data: Dict[str, Any]) -> str:
        """Export data to CSV format"""
        df = pd.DataFrame(data.get('data', {}))
        return df.to_csv(index=False)
    
    async def _export_excel(self, data: Dict[str, Any]) -> bytes:
        """Export data to Excel format"""
        import io
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, sheet_data in data.get('data', {}).items():
                df = pd.DataFrame(sheet_data)
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        
        return output.getvalue()
    
    def _calculate_next_run(self, schedule: str) -> str:
        """Calculate next run time based on schedule"""
        now = datetime.utcnow()
        
        if schedule == "daily":
            next_run = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        elif schedule == "weekly":
            next_run = now.replace(hour=0, minute=0, second=0) + timedelta(days=7 - now.weekday())
        else:  # monthly
            next_run = now.replace(day=1, hour=0, minute=0, second=0) + timedelta(days=32)
            next_run = next_run.replace(day=1)
        
        return next_run.isoformat()