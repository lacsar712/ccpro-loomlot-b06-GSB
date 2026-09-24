from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.user import User
from app.schemas.fastness_check import (
    FastnessCheckCreate,
    FastnessCheckUpdate,
    FastnessCheckOut,
    FastnessDispatch,
)

router = APIRouter(prefix="/api/fastness-checks", tags=["fastness-checks"])

# 外发后锁定的测值字段：耐洗、耐摩擦、温度
LOCKED_FIELDS = {"wash_fastness", "rub_fastness", "temp_c"}


def _parse_day(date_str: str) -> tuple[datetime, datetime]:
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


@router.get("", response_model=List[FastnessCheckOut])
def list_checks(
    dye_lot_id: Optional[int] = Query(None, alias="dyeLotId"),
    dispatched: bool = Query(False, description="true=仅外发清单；默认 false=仅未外发"),
    day: Optional[str] = Query(None, description="按检测日过滤 YYYY-MM-DD（外发清单口径）"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """默认列表只显示未外发；dispatched=true 为仅外发清单，可按日过滤。"""
    q = db.query(FastnessCheck)
    if dispatched:
        q = q.filter(FastnessCheck.outbound_no.isnot(None))
    else:
        q = q.filter(FastnessCheck.outbound_no.is_(None))
    if dye_lot_id is not None:
        q = q.filter(FastnessCheck.dye_lot_id == dye_lot_id)
    if day is not None:
        start, end = _parse_day(day)
        q = q.filter(FastnessCheck.checked_at >= start, FastnessCheck.checked_at < end)
    return q.order_by(FastnessCheck.id.desc()).all()


@router.post("", response_model=FastnessCheckOut, status_code=status.HTTP_201_CREATED)
def create_check(
    payload: FastnessCheckCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # 操作员可建；新建时外发编号一律为空
    lot = (
        db.query(DyeLot)
        .filter(DyeLot.id == payload.dye_lot_id)
    ).first()
    if not lot:
        raise HTTPException(status_code=400, detail="染程不存在")
    item = FastnessCheck(
        dye_lot_id=payload.dye_lot_id,
        dye_house_id=lot.vat.dye_house_id,
        checked_at=payload.checked_at,
        wash_fastness=payload.wash_fastness,
        rub_fastness=payload.rub_fastness,
        temp_c=payload.temp_c,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{check_id}", response_model=FastnessCheckOut)
def get_check(
    check_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(FastnessCheck).filter(FastnessCheck.id == check_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="色牢度抽检不存在")
    return item


@router.put("/{check_id}", response_model=FastnessCheckOut)
def update_check(
    check_id: int,
    payload: FastnessCheckUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # 操作员可改未外发；已外发后耐洗/耐摩擦/温度一律锁定
    item = db.query(FastnessCheck).filter(FastnessCheck.id == check_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="色牢度抽检不存在")

    data = payload.model_dump(exclude_unset=True)

    if item.outbound_no:
        changed_locked = [
            name
            for name in LOCKED_FIELDS
            if name in data and getattr(item, name) != data[name]
        ]
        if changed_locked:
            raise HTTPException(
                status_code=409,
                detail=f"该抽检已外发（编号 {item.outbound_no}），耐洗、耐摩擦、温度已锁定不可修改",
            )
        if "dye_lot_id" in data and data["dye_lot_id"] != item.dye_lot_id:
            raise HTTPException(
                status_code=409,
                detail=f"该抽检已外发（编号 {item.outbound_no}），不可改挂染程",
            )

    if "dye_lot_id" in data and data["dye_lot_id"] != item.dye_lot_id:
        lot = db.query(DyeLot).filter(DyeLot.id == data["dye_lot_id"]).first()
        if not lot:
            raise HTTPException(status_code=400, detail="染程不存在")
        # 改挂染程时归属染坊随之变更
        data["dye_house_id"] = lot.vat.dye_house_id

    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{check_id}/dispatch", response_model=FastnessCheckOut)
def dispatch_check(
    check_id: int,
    payload: FastnessDispatch,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """外发：写入唯一外发编号（同坊唯一）。仅主管可操作。"""
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="仅染坊主管可执行实验室外发")

    item = db.query(FastnessCheck).filter(FastnessCheck.id == check_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="色牢度抽检不存在")
    if item.outbound_no:
        raise HTTPException(
            status_code=409,
            detail=f"该抽检已外发，外发编号为 {item.outbound_no}，不可重复外发",
        )

    outbound_no = payload.outbound_no and payload.outbound_no.strip()
    if not outbound_no:
        outbound_no = f"OUT-{item.dye_house_id:02d}-{datetime.now(timezone.utc):%Y%m%d}-{item.id:04d}"

    clash = (
        db.query(FastnessCheck)
        .filter(
            FastnessCheck.dye_house_id == item.dye_house_id,
            FastnessCheck.outbound_no == outbound_no,
        )
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=409,
            detail=f"外发编号「{outbound_no}」在本染坊已存在",
        )

    item.outbound_no = outbound_no
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"外发编号「{outbound_no}」在本染坊已存在",
        )
    db.refresh(item)
    return item


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_check(
    check_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(FastnessCheck).filter(FastnessCheck.id == check_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="色牢度抽检不存在")
    if item.outbound_no:
        raise HTTPException(
            status_code=409,
            detail=f"该抽检已外发（编号 {item.outbound_no}），不可删除",
        )
    db.delete(item)
    db.commit()
