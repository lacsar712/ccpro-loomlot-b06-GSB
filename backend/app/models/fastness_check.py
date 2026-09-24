from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dye_house import DyeHouse
    from app.models.dye_lot import DyeLot


class FastnessCheck(Base):
    __tablename__ = "fastness_checks"
    # 外发编号在同一染坊内唯一
    __table_args__ = (
        UniqueConstraint("dye_house_id", "outbound_no", name="uq_house_outbound_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dye_lot_id: Mapped[int] = mapped_column(ForeignKey("dye_lots.id"), nullable=False, index=True)
    dye_house_id: Mapped[int] = mapped_column(ForeignKey("dye_houses.id"), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    wash_fastness: Mapped[int] = mapped_column(Integer, nullable=False)
    rub_fastness: Mapped[float] = mapped_column(Float, nullable=False)
    temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 外发编号：新建为空；一旦写入即视为已外发，测值锁定
    outbound_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    dye_lot: Mapped["DyeLot"] = relationship("DyeLot", back_populates="fastness_checks")
    dye_house: Mapped["DyeHouse"] = relationship("DyeHouse")
