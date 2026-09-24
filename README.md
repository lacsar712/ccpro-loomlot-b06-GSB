# LoomLot-01 · 染坊缸染与色牢度抽检

靛蓝染坊台：按 **染坊 → 染缸 → 染程 → 色牢度** 工序推进，聚焦缸染调度与抽检，不是库存出入库系统。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Backend | FastAPI + SQLAlchemy 2 + Pydantic v2 + Postgres + JWT |
| Frontend | Svelte 4 + Vite + svelte-spa-router |
| 部署 | docker-compose（db + backend + frontend/nginx） |

## 端口

| 服务 | 端口 |
| --- | --- |
| 前端 | **3600** |
| 后端 API | **8600** |
| PostgreSQL | **5439** |

数据库账号：`loomlot` / `loomlot` / 库名 `loomlot`。

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 染坊主管 |
| `dyer` | `123456` | 染程操作员 |

容器启动时 entrypoint 自动建表并 seed。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\LoomLot\LoomLot-01
docker compose up -d --build
```

浏览器：http://localhost:3600  
API：http://localhost:8600/api/health

停止：

```bash
docker compose down
```

## 业务实体

1. **DyeHouse** — `name`, `waterNote`, `notes`
2. **Vat** — `dyeHouseId`, `vatCode`, `fiberType`, `capacityL`, `status` ∈ `ready|dyeing|drain`
3. **DyeLot** — `vatId`, `recipeName`, `fabricKg`, `startedAt`, `operatorName`
4. **FastnessCheck** — `dyeLotId`, `checkedAt`, `washFastness`(1–5), `rubFastness`(>0), `tempC`, `notes`, `labRefNo`（实验室外发编号，可空）

### 规则

- 仅当染缸状态为 `ready` 或 `dyeing` 时可新建染程，否则 409
- 新建染程后，染缸状态自动设为 `dyeing`
- 可选接口：`POST /api/vats/{id}/drain` 将染缸置为 `drain`

### 色牢度外发与锁定

- 新建抽检时 `labRefNo` 恒为空（未外发），接口不接受外发编号入参
- 主管（admin）调用 `POST /api/fastness-checks/{id}/dispatch`，body `{ "labRefNo": "..." }` 写入外发编号；编号**同染坊唯一**，冲突返回 **409 中文**（`同坊外发编号已存在`）；重复外发 409（`该抽检已外发，不可重复外发`）；操作员（dyer）调用返回 403
- 外发编号非空即**已外发**，此后耐洗 `washFastness`、摩擦 `rubFastness`、温度 `tempC` 一律不可改，尝试修改返回 **409 中文**（`已外发抽检测值已锁定，不可修改…`）；已外发记录也不可改挂染程、不可删除
- **列表分流**：`GET /api/fastness-checks` 默认（`outbound=false`）只返回未外发；`outbound=true` 为外发清单（仅已外发），支持 `day=YYYY-MM-DD`（UTC 日历日）按检测日过滤
- 看板「今日已外发抽检」只计已外发，按 UTC 当日历日统计，与外发清单 `?outbound=true&day=<今日UTC>` 行数严格一致；未外发不混入
- 操作员可新建、修改未外发抽检；外发动作仅主管
- 种子数据含未外发与已外发抽检各至少一条

## 主要 API

- `POST /api/auth/login`（OAuth2 表单）
- `GET /api/auth/me`
- `GET/POST/PUT/DELETE /api/dye-houses`
- `GET/POST/PUT/DELETE /api/vats` · `POST /api/vats/{id}/drain`
- `GET/POST/PUT/DELETE /api/dye-lots`
- `GET/POST/PUT/DELETE /api/fastness-checks`（GET 支持 `outbound`、`day` 分流过滤）· `POST /api/fastness-checks/{id}/dispatch`
- `GET /api/dashboard/stats`

除登录外需 `Authorization: Bearer <token>`。字段对外为 camelCase。

## 目录

```
LoomLot-01/
├── docker-compose.yml
├── backend/          # FastAPI
├── frontend/         # Svelte 4 + Vite + nginx
└── README.md
```

## 本地开发

### 数据库

```bash
docker compose up -d db
```

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg2://loomlot:loomlot@127.0.0.1:5439/loomlot"
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
uvicorn app.main:app --reload --port 8600
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发态 Vite 将 `/api` 代理到 `http://127.0.0.1:8600`。
