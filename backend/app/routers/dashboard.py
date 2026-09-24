from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.user import User
from app.models.vat import Vat
from app.schemas.dashboard import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    return DashboardStats(
        dye_house_total=db.query(func.count(DyeHouse.id)).scalar() or 0,
        vat_ready_count=db.query(func.count(Vat.id)).filter(Vat.status == "ready").scalar() or 0,
        vat_dyeing_count=db.query(func.count(Vat.id)).filter(Vat.status == "dyeing").scalar() or 0,
        lots_last_7d=(
            db.query(func.count(DyeLot.id))
            .filter(DyeLot.started_at >= now - timedelta(days=7))
            .scalar()
            or 0
        ),
        # 近一天抽检只计已外发（lab_ref_no 非空），按 UTC 当日历日统计；
        # 必须与 GET /fastness-checks?outbound=true&day=<今日UTC> 的行数一致（同源同口径）。
        checks_last_24h=(
            db.query(func.count(FastnessCheck.id))
            .filter(
                FastnessCheck.checked_at >= today_start,
                FastnessCheck.lab_ref_no.isnot(None),
            )
            .scalar()
            or 0
        ),
    )
