from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.database import SessionLocal
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.user import User
from app.models.vat import Vat


def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(
                        username="admin",
                        hashed_password=hash_password("123456"),
                        role="admin",
                        display_name="染坊主管",
                    ),
                    User(
                        username="dyer",
                        hashed_password=hash_password("123456"),
                        role="dyer",
                        display_name="染程操作员",
                    ),
                ]
            )
            db.commit()

        if db.query(DyeHouse).count() == 0:
            h1 = DyeHouse(
                name="蓝靛一号坊",
                water_note="软化井水，硬度约 80ppm",
                notes="主做棉麻靛蓝与草木染",
            )
            h2 = DyeHouse(
                name="青石二号坊",
                water_note="河溪砂滤水，日供约 12 吨",
                notes="专职丝绢与混纺缸染",
            )
            db.add_all([h1, h2])
            db.flush()

            v1 = Vat(
                dye_house_id=h1.id,
                vat_code="V-01",
                fiber_type="棉",
                capacity_l=800.0,
                status="dyeing",
            )
            v2 = Vat(
                dye_house_id=h1.id,
                vat_code="V-02",
                fiber_type="麻",
                capacity_l=600.0,
                status="ready",
            )
            v3 = Vat(
                dye_house_id=h2.id,
                vat_code="S-01",
                fiber_type="丝",
                capacity_l=350.0,
                status="ready",
            )
            v4 = Vat(
                dye_house_id=h2.id,
                vat_code="S-02",
                fiber_type="混纺",
                capacity_l=500.0,
                status="drain",
            )
            db.add_all([v1, v2, v3, v4])
            db.flush()

            now = datetime.now(timezone.utc)
            lot1 = DyeLot(
                vat_id=v1.id,
                recipe_name="靛蓝冷染三浸",
                fabric_kg=42.5,
                started_at=now - timedelta(hours=6),
                operator_name="染程操作员",
            )
            lot2 = DyeLot(
                vat_id=v3.id,
                recipe_name="青蓝套染",
                fabric_kg=18.0,
                started_at=now - timedelta(days=2),
                operator_name="染坊主管",
            )
            db.add_all([lot1, lot2])
            db.flush()

            # lot2 was on ready vat historically — keep v3 ready for demo create path
            # Re-set: creating lot2 would have set dyeing; for seed we leave one dyeing + one ready
            v3.status = "ready"
            db.add_all(
                [
                    # 未外发：外发编号为空，操作员仍可建改
                    FastnessCheck(
                        dye_lot_id=lot1.id,
                        dye_house_id=h1.id,
                        checked_at=now - timedelta(hours=2),
                        wash_fastness=4,
                        rub_fastness=3.5,
                        temp_c=40.0,
                        notes="湿摩略偏，可出货",
                        lab_ref_no=None,
                    ),
                    # 已外发：外发编号非空，耐洗/摩擦/温度锁定（检测时间取当日，外发清单默认今日可见）
                    FastnessCheck(
                        dye_lot_id=lot2.id,
                        dye_house_id=h2.id,
                        checked_at=now - timedelta(minutes=30),
                        wash_fastness=5,
                        rub_fastness=4.0,
                        temp_c=37.0,
                        notes="实验室回件合格",
                        lab_ref_no=f"LAB-{now.strftime('%Y%m%d')}-01",
                    ),
                ]
            )
            db.commit()
            print("Seed data inserted.")
        else:
            print("Seed skipped (data exists).")

        # 既有卷幂等补齐：保证未外发/已外发各至少一条可演示
        now = datetime.now(timezone.utc)
        added = False
        if db.query(FastnessCheck).filter(FastnessCheck.lab_ref_no.is_(None)).count() == 0:
            lot = (
                db.query(DyeLot)
                .join(Vat, Vat.id == DyeLot.vat_id)
                .order_by(DyeLot.id)
                .first()
            )
            if lot:
                vat = db.query(Vat).filter(Vat.id == lot.vat_id).first()
                db.add(
                    FastnessCheck(
                        dye_lot_id=lot.id,
                        dye_house_id=vat.dye_house_id,
                        checked_at=now - timedelta(hours=1),
                        wash_fastness=4,
                        rub_fastness=3.5,
                        temp_c=40.0,
                        notes="种子补齐：未外发",
                        lab_ref_no=None,
                    )
                )
                added = True
        if db.query(FastnessCheck).filter(FastnessCheck.lab_ref_no.isnot(None)).count() == 0:
            lot = (
                db.query(DyeLot)
                .join(Vat, Vat.id == DyeLot.vat_id)
                .order_by(DyeLot.id.desc())
                .first()
            )
            if lot:
                vat = db.query(Vat).filter(Vat.id == lot.vat_id).first()
                ref = f"LAB-{now.strftime('%Y%m%d')}-SEED"
                # 同坊撞号时换一个号
                while (
                    db.query(FastnessCheck.id)
                    .filter(FastnessCheck.dye_house_id == vat.dye_house_id, FastnessCheck.lab_ref_no == ref)
                    .first()
                ):
                    ref += "X"
                db.add(
                    FastnessCheck(
                        dye_lot_id=lot.id,
                        dye_house_id=vat.dye_house_id,
                        checked_at=now - timedelta(minutes=30),
                        wash_fastness=5,
                        rub_fastness=4.0,
                        temp_c=37.0,
                        notes="种子补齐：已外发",
                        lab_ref_no=ref,
                    )
                )
                added = True
        if added:
            db.commit()
            print("Seed supplemented with pending/outbound fastness checks.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
