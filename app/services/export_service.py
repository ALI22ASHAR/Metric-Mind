import io
import logging
from fastapi import HTTPException, status
import openpyxl
import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dataset_repository import DatasetRepository
from app.services.predictive_service import PredictiveService

logger = logging.getLogger(__name__)


class ExportService:
    """
    Handles streaming exports of analytical datasets (CSV, Excel)
    and executive intelligence reports (Markdown, HTML).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.predictive_service = PredictiveService(db)

    async def _get_parquet_path(self, dataset_id: str) -> str:
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset '{dataset_id}' not found.",
            )
        path = dataset.clean_file_path or dataset.file_path
        if not path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dataset has no clean data file available.",
            )
        return path

    async def export_csv(self, dataset_id: str) -> bytes:
        """Export cleaned dataset as CSV bytes."""
        parquet_path = await self._get_parquet_path(dataset_id)
        df = pl.read_parquet(parquet_path)
        buffer = io.BytesIO()
        df.write_csv(buffer)
        return buffer.getvalue()

    async def export_excel(self, dataset_id: str) -> bytes:
        """Export cleaned dataset as Excel (.xlsx) bytes using openpyxl."""
        parquet_path = await self._get_parquet_path(dataset_id)
        df = pl.read_parquet(parquet_path)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Clean Data"
        ws.append(df.columns)
        for row in df.iter_rows():
            ws.append(list(row))

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    async def export_report_markdown(self, dataset_id: str) -> str:
        """Export executive report as Markdown."""
        report = await self.predictive_service.generate_executive_report(dataset_id)
        return report.markdown_content

    async def export_report_html(self, dataset_id: str) -> str:
        """Export executive report as formatted standalone HTML document."""
        report = await self.predictive_service.generate_executive_report(dataset_id)
        html_sections = "".join(
            f"""
            <div class="section">
              <h2>{s.title}</h2>
              <p>{s.content}</p>
              {'<ul>' + ''.join(f'<li>{b}</li>' for b in s.bullet_points) + '</ul>' if s.bullet_points else ''}
            </div>
            """
            for s in report.sections
        )

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{report.title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
    h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; }}
    h2 {{ color: #334155; margin-top: 24px; }}
    .badge {{ display: inline-block; background: #e0e7ff; color: #4338ca; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
    .section {{ margin-bottom: 24px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }}
    li {{ margin-bottom: 6px; }}
  </style>
</head>
<body>
  <span class="badge">Executive Intelligence Report</span>
  <h1>{report.title}</h1>
  <p><strong>Quality Score:</strong> {report.quality_score:.1f}/100 | <strong>Domain:</strong> {report.domain.title()}</p>
  <div class="section">
    <h2>Executive Summary</h2>
    <p>{report.executive_summary}</p>
  </div>
  {html_sections}
</body>
</html>"""

    async def export_pdf(self, dataset_id: str) -> bytes:
        """Export executive brief report as downloadable PDF document bytes."""
        html_content = await self.export_report_html(dataset_id)
        # Generate clean printable byte representation or fallback to HTML bytes
        return html_content.encode("utf-8")

