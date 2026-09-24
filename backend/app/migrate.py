"""轻量幂等升级：为既有库卷补齐色牢度外发字段。

create_all 不会修改已存在的表，B06 之前创建的库需要补：
- fastness_checks.dye_house_id（NOT NULL，按 染程→染缸 回填）
- fastness_checks.lab_ref_no（可空）
- 同坊外发编号部分唯一索引
"""

from sqlalchemy import text

from app.database import engine


PG_SQL = [
    "ALTER TABLE fastness_checks ADD COLUMN IF NOT EXISTS dye_house_id INTEGER",
    """
    UPDATE fastness_checks fc
    SET dye_house_id = v.dye_house_id
    FROM dye_lots l
    JOIN vats v ON v.id = l.vat_id
    WHERE fc.dye_lot_id = l.id AND fc.dye_house_id IS NULL
    """,
    "ALTER TABLE fastness_checks ALTER COLUMN dye_house_id SET NOT NULL",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'fk_fastness_checks_dye_house'
        ) THEN
            ALTER TABLE fastness_checks
                ADD CONSTRAINT fk_fastness_checks_dye_house
                FOREIGN KEY (dye_house_id) REFERENCES dye_houses(id);
        END IF;
    END $$;
    """,
    "ALTER TABLE fastness_checks ADD COLUMN IF NOT EXISTS lab_ref_no VARCHAR(64)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_house_lab_ref_no
    ON fastness_checks (lab_ref_no, dye_house_id)
    WHERE lab_ref_no IS NOT NULL
    """,
]


def migrate() -> None:
    if engine.dialect.name != "postgresql":
        print("Migration skipped (non-postgresql dialect).")
        return
    with engine.begin() as conn:
        for stmt in PG_SQL:
            conn.execute(text(stmt))
    print("Migration up to date.")


if __name__ == "__main__":
    migrate()
