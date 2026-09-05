import logging
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.export_service import ExportService
from app.api.v1.dependencies import require_dataset_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets/{dataset_id}/export", tags=["Export Engine"], dependencies=[Depends(require_dataset_access)])


@router.get(
    "/csv",
    status_code=status.HTTP_200_OK,
    summary="Download cleaned dataset as CSV",
    description="Streams clean Parquet data converted to CSV file format.",
)
async def export_csv(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    service = ExportService(db)
    csv_bytes = await service.export_csv(dataset_id)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}_clean.csv"'},
    )


@router.get(
    "/excel",
    status_code=status.HTTP_200_OK,
    summary="Download cleaned dataset as Excel (.xlsx)",
    description="Streams clean Parquet data converted to standard Excel worksheet format.",
)
async def export_excel(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    service = ExportService(db)
    excel_bytes = await service.export_excel(dataset_id)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}_clean.xlsx"'},
    )


@router.get(
    "/report",
    status_code=status.HTTP_200_OK,
    summary="Download executive report in Markdown or HTML",
    description="Returns formatted standalone document of the executive narrative report.",
)
async def export_report(
    dataset_id: str,
    format: str = "markdown",  # "markdown" or "html"
    db: AsyncSession = Depends(get_db),
) -> Response:
    service = ExportService(db)
    if format.lower() == "html":
        html_content = await service.export_report_html(dataset_id)
        return Response(content=html_content, media_type="text/html")
    
    md_content = await service.export_report_markdown(dataset_id)
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}_report.md"'},
    )


@router.get(
    "/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download executive report as PDF document",
    description="Returns high-resolution formatted executive report as a PDF document.",
)
async def export_pdf(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    service = ExportService(db)
    pdf_bytes = await service.export_pdf(dataset_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}_executive_brief.pdf"'},
    )

