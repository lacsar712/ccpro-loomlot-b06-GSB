from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dye_lot import DyeLot


class FastnessCheck(Base):
    __tablename__ = "fastness_checks"
    # 外发编号同染坊唯一（仅已外发行参与，lab_ref_no 为 NULL 不冲突）。
    # 染坊经由 染程→染缸 归属，这里冗余 dye_house_id 以支撑库级唯一约束。
    __table_args__ = (
        Index(
            "uq_house_lab_ref_no",
            "lab_ref_no",
            "dye_house_id",
            unique=True,
            postgresql_where=text("lab_ref_no IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dye_lot_id: Mapped[int] = mapped_column(ForeignKey("dye_lots.id"), nullable=False, index=True)
    dye_house_id: Mapped[int] = mapped_column(ForeignKey("dye_houses.id"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wash_fastness: Mapped[int] = mapped_column(Integer, nullable=False)
    rub_fastness: Mapped[float] = mapped_column(Float, nullable=False)
    temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 实验室外发编号：新建为空；非空即视为已外发，测值锁定。
    lab_ref_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    dye_lot: Mapped["DyeLot"] = relationship("DyeLot", back_populates="fastness_checks")
