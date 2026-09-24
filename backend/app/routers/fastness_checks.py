from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.user import User
from app.models.vat import Vat
from app.schemas.fastness_check import (
    FastnessCheckCreate,
    FastnessCheckDispatch,
    FastnessCheckOut,
    FastnessCheckUpdate,
)

router = APIRouter(prefix="/api/fastness-checks", tags=["fastness-checks"])

# 外发后锁定的测值字段
LOCKED_FIELDS = {
    "wash_fastness": "耐洗牢度",
    "rub_fastness": "摩擦牢度",
    "temp_c": "温度",
}


@router.get("", response_model=List[FastnessCheckOut])
def list_checks(
    dye_lot_id: Optional[int] = Query(None, alias="dyeLotId"),
    outbound: bool = Query(False, description="true=仅外发清单；false=默认仅未外发"),
    day: Optional[date] = Query(None, description="按检测日过滤（UTC 日历日，YYYY-MM-DD）"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(FastnessCheck)
    if dye_lot_id is not None:
        q = q.filter(FastnessCheck.dye_lot_id == dye_lot_id)
    if outbound:
        q = q.filter(FastnessCheck.lab_ref_no.isnot(None))
    else:
        q = q.filter(FastnessCheck.lab_ref_no.is_(None))
    if day is not None:
        start = datetime.combine(day, time.min, tzinfo=timezone.utc)
        q = q.filter(
            FastnessCheck.checked_at >= start,
            FastnessCheck.checked_at < start + timedelta(days=1),
        )
    return q.order_by(FastnessCheck.id.desc()).all()


@router.post("", response_model=FastnessCheckOut, status_code=status.HTTP_201_CREATED)
def create_check(
    payload: FastnessCheckCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # 操作员即可登记；外发编号永远不由新建写入
    lot = db.query(DyeLot).filter(DyeLot.id == payload.dye_lot_id).first()
    if not lot:
        raise HTTPException(status_code=400, detail="染程不存在")
    vat = db.query(Vat).filter(Vat.id == lot.vat_id).first()
    item = FastnessCheck(
        dye_lot_id=payload.dye_lot_id,
        dye_house_id=vat.dye_house_id,
        checked_at=payload.checked_at,
        wash_fastness=payload.wash_fastness,
        rub_fastness=payload.rub_fastness,
        temp_c=payload.temp_c,
        notes=payload.notes,
        lab_ref_no=None,
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


@router.post(
    "/{check_id}/dispatch",
    response_model=FastnessCheckOut,
    dependencies=[Depends(require_admin)],
)
def dispatch_check(
    check_id: int,
    payload: FastnessCheckDispatch,
    db: Session = Depends(get_db),
):
    """主管外发：写入唯一外发编号（同染坊唯一），写入后测值锁定。"""
    item = db.query(FastnessCheck).filter(FastnessCheck.id == check_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="色牢度抽检不存在")
    if item.lab_ref_no is not None:
        raise HTTPException(status_code=409, detail="该抽检已外发，不可重复外发")

    ref = payload.lab_ref_no.strip()
    clash = (
        db.query(FastnessCheck.id)
        .filter(
            FastnessCheck.dye_house_id == item.dye_house_id,
            FastnessCheck.lab_ref_no == ref,
        )
        .first()
    )
    if clash:
        raise HTTPException(status_code=409, detail="同坊外发编号已存在")

    item.lab_ref_no = ref
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="同坊外发编号已存在")
    db.refresh(item)
    return item


@router.put("/{check_id}", response_model=FastnessCheckOut)
def update_check(
    check_id: int,
    payload: FastnessCheckUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(FastnessCheck).filter(FastnessCheck.id == check_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="色牢度抽检不存在")
    data = payload.model_dump(exclude_unset=True)

    if item.lab_ref_no is not None:
        changed_locked = [
            label
            for field, label in LOCKED_FIELDS.items()
            if field in data and getattr(item, field) != data[field]
        ]
        if changed_locked:
            raise HTTPException(
                status_code=409,
                detail=f"已外发抽检测值已锁定，不可修改{'、'.join(changed_locked)}",
            )
        if "dye_lot_id" in data and data["dye_lot_id"] != item.dye_lot_id:
            raise HTTPException(status_code=409, detail="已外发抽检不可改挂染程")

    if "dye_lot_id" in data and data["dye_lot_id"] != item.dye_lot_id:
        lot = db.query(DyeLot).filter(DyeLot.id == data["dye_lot_id"]).first()
        if not lot:
            raise HTTPException(status_code=400, detail="染程不存在")
        vat = db.query(Vat).filter(Vat.id == lot.vat_id).first()
        data["dye_house_id"] = vat.dye_house_id

    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
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
    if item.lab_ref_no is not None:
        raise HTTPException(status_code=409, detail="已外发抽检已锁定，不可删除")
    db.delete(item)
    db.commit()
