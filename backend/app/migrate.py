"""幂等轻量迁移：为色牢度抽检补充实验室外发编号与染坊归属。

- 新库由 Base.metadata.create_all 直接建出，本脚本全部跳过；
- 旧库补上 dye_house_id、outbound_no 列，回填历史数据并建立同坊唯一约束。
"""

from sqlalchemy import text

from app.database import engine


SQL_STEPS = [
    # 染坊归属（外发编号同坊唯一所需）
    "ALTER TABLE fastness_checks ADD COLUMN IF NOT EXISTS dye_house_id INTEGER REFERENCES dye_houses(id)",
    # 历史数据按 染程 -> 染缸 -> 染坊 回填
    """
    UPDATE fastness_checks fc
    SET dye_house_id = v.dye_house_id
    FROM dye_lots dl
    JOIN vats v ON v.id = dl.vat_id
    WHERE fc.dye_lot_id = dl.id AND fc.dye_house_id IS NULL
    """,
    "ALTER TABLE fastness_checks ALTER COLUMN dye_house_id SET NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_fastness_checks_dye_house_id ON fastness_checks (dye_house_id)",
    # 实验室外发编号
    "ALTER TABLE fastness_checks ADD COLUMN IF NOT EXISTS outbound_no VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS ix_fastness_checks_outbound_no ON fastness_checks (outbound_no)",
    # 同坊唯一（Postgres 唯一索引中多个 NULL 互不冲突，未外发记录不受影响）
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_house_outbound_no ON fastness_checks (dye_house_id, outbound_no)",
]


def migrate() -> None:
    with engine.begin() as conn:
        for stmt in SQL_STEPS:
            conn.execute(text(stmt))
    print("Migration up to date.")


if __name__ == "__main__":
    migrate()
