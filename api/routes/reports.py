"""
Reports endpoint — generate CSV/JSON reports for channels over a time range.
"""
import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Channel, Error, Metric
from db.schemas import ReportRequest, ReportResponse

router = APIRouter()


@router.post("/reports/generate", response_model=ReportResponse)
async def generate_report(payload: ReportRequest, db: AsyncSession = Depends(get_db)):
    """Generate a JSON summary report for the requested channels and time range."""
    channel_q = select(Channel).where(Channel.is_active == True)
    if payload.channel_ids:
        channel_q = channel_q.where(Channel.id.in_(payload.channel_ids))
    channels = (await db.execute(channel_q)).scalars().all()

    report_data = []
    for ch in channels:
        entry: dict = {"channel_id": str(ch.id), "channel_name": ch.name, "group": ch.group}

        if payload.include_metrics:
            agg = (await db.execute(
                select(
                    func.avg(Metric.bitrate).label("avg_bitrate"),
                    func.count(Metric.id).label("total"),
                    func.sum(Metric.is_available.cast(int)).label("available"),
                    func.avg(Metric.response_time).label("avg_rt"),
                ).where(
                    Metric.channel_id == ch.id,
                    Metric.timestamp >= payload.start_time,
                    Metric.timestamp <= payload.end_time,
                )
            )).one()

            total = agg.total or 0
            available = agg.available or 0
            entry["avg_bitrate_kbps"] = round(agg.avg_bitrate, 1) if agg.avg_bitrate else None
            entry["avg_response_time_ms"] = round(agg.avg_rt, 1) if agg.avg_rt else None
            entry["availability_pct"] = round(available / total * 100, 2) if total > 0 else 0
            entry["metric_samples"] = total

        if payload.include_errors:
            error_counts = (await db.execute(
                select(Error.error_type, func.count(Error.id).label("cnt"))
                .where(
                    Error.channel_id == ch.id,
                    Error.timestamp >= payload.start_time,
                    Error.timestamp <= payload.end_time,
                )
                .group_by(Error.error_type)
            )).all()
            entry["errors"] = {r[0]: r[1] for r in error_counts}
            entry["total_errors"] = sum(r[1] for r in error_counts)

        report_data.append(entry)

    return ReportResponse(
        report_id=str(uuid.uuid4()),
        generated_at=datetime.now(timezone.utc),
        period_start=payload.start_time,
        period_end=payload.end_time,
        channel_count=len(channels),
        data=report_data,
    )


@router.post("/reports/export/csv")
async def export_csv(payload: ReportRequest, db: AsyncSession = Depends(get_db)):
    """Export report as CSV file download."""
    report = await generate_report(payload, db)

    output = io.StringIO()
    if report.data:
        writer = csv.DictWriter(output, fieldnames=report.data[0].keys())
        writer.writeheader()
        for row in report.data:
            # Flatten nested dicts
            flat = {k: (str(v) if isinstance(v, dict) else v) for k, v in row.items()}
            writer.writerow(flat)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=ott_report_{report.report_id[:8]}.csv"
        },
    )
