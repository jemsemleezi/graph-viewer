# graph-viewer 项目备忘录

_最后更新：2026-03-29_

## 项目概况

- **路径：** `C:\Users\15967\.openclaw\workspace\projects\graph-viewer`
- **技术栈：** 纯 HTML + JavaScript 前端，vis-network 9.1.9 力导向图，后端 Flask（Python）
- **主文件：** `static/index.html`（前端），`server.py`（后端）
- **服务端口：** 7892
- **数据接口：** 后端 `/api/graph` 返回 `{ nodes, edges }`
- **启动方式：** 双击 `启动图谱.vbs`（托盘模式）

### 节点数据结构
```json
{ "id": "", "name": "", "type": "SKILL|TASK|EVENT", "description": "", "content": "", "pagerank": 0, "community_id": "", "status": "active" }
```

### 边数据结构
```json
{ "id": "", "from_id": "", "to_id": "", "type": "USED_SKILL|SOLVED_BY|REQUIRES|PATCHES|CONFLICTS_WITH", "instruction": "", "condition": "" }
```

### 颜色方案
```js
const TYPE_COLORS = { SKILL: '#34d399', TASK: '#60a5fa', EVENT: '#f87171' };
const EDGE_COLORS = { USED_SKILL: '#a78bfa', SOLVED_BY: '#fb923c', REQUIRES: '#38bdf8', PATCHES: '#f9a8d4', CONFLICTS_WITH: '#fbbf24' };
```

---

## 文件清单（当前状态）

| 文件 | 说明 | 状态 |
|------|------|------|
| `static/index.html` | 前端主文件 | ✅ 正常 |
| `server.py` | Flask 后端 | ✅ 正常 |
| `tray.py` | 系统托盘启动器 | ✅ 正常 |
| `启动图谱.vbs` | 双击启动入口（无黑窗口） | ✅ 正常 |
| `start.ps1` | PowerShell 启动脚本（备用） | ✅ 正常 |
| `README.md` | 用户文档 | ✅ 已创建 |
| `MEMO.md` | 本文件 | ✅ 活跃 |

---

## 后端接口（server.py）✅ 全部正常

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/graph` | GET | 返回当前图谱数据（SQLite 或内存 JSON）|
| `/api/node/<id>` | GET | 获取单节点详情 |
| `/api/node` | POST | 新增节点 |
| `/api/node/<id>` | PUT | 更新节点 |
| `/api/node/<id>` | DELETE | 删除节点及关联边 |
| `/api/edge` | POST | 新增关系边 |
| `/api/edge/<id>` | DELETE | 删除关系边 |
| `/api/switch-db` | POST | 切换 SQLite 文件路径 `{"path": "..."}` |
| `/api/load-json` | POST | 上传 JSON 图谱 `{"nodes":[...],"edges":[...]}` |
| `/api/reset-db` | POST | 恢复默认数据库 |
| `/api/set-default-db` | POST | 将当前数据库持久化为默认 |

---

## 前端功能（✅ 全部完成）

### 图谱视图
- [x] 力导向图展示（vis-network 9.1.9）
- [x] 节点按类型着色，边按关系类型着色
- [x] 点击节点显示详情面板
- [x] 节点编辑（名称、描述、内容）
- [x] 节点删除（同步删除关联边）
- [x] 搜索过滤节点
- [x] 按类型筛选（SKILL / TASK / EVENT）
- [x] 手动刷新 + 定时自动刷新（10s）
- [x] 物理引擎优化（稳定后关闭抖动）
- [x] 稳定完成后自动 fit 适应屏幕

### 数据管理
- [x] 新增节点表单
- [x] 新增关系表单
- [x] 表格视图（列表形式浏览所有节点）
- [x] 载入图谱（SQLite 路径 / JSON 文件上传）
- [x] 当前数据源状态显示
- [x] 恢复默认数据库按钮
- [x] 设置当前数据库为默认按钮

### 路径处理
- [x] 自动剥离 U+202A 等 Unicode 方向控制字符（从文件管理器复制路径时附带）

---

## 托盘启动器（tray.py）✅ 正常

- 双击 `启动图谱.vbs` 触发，无命令窗口弹出
- 启动时自动清理 7892 端口旧进程（taskkill /F /T）
- 托盘右键菜单：打开图谱 / 退出
- 退出托盘时同步终止 server.py 进程树
- 参考 gold-price 项目实现（`setup` 回调 + `icon.visible = True`）

---

## 待改进项（来源：GLM5 代码审查 2026-03-29）

### 🔴 高优先级

| 问题 | 位置 | 改进方案 |
|------|------|----------|
| 硬编码用户路径 `C:\Users\15967` | `server.py` `_BUILTIN_DEFAULT` | 改用 `os.path.expanduser('~')` 动态获取用户目录 |
| 数据库连接未用上下文管理器 | `server.py` 各路由 | 全部改为 `with DbConnectionManager() as conn:` 防止连接泄漏导致 DB locked |
| 删除节点时 `PRAGMA foreign_keys=OFF` | `server.py` `delete_node` | 改为先手动删关联边再删节点，保持外键约束开启 |

### 🟡 中优先级

| 问题 | 位置 | 改进方案 |
|------|------|----------|
| 全局变量线程不安全 | `server.py` `_current_db_path` / `_json_graph` | 迁移至 Flask `g` 对象或加锁保护，避免并发写冲突 |
| `import` 语句在循环内部 | `tray.py` 健康检查循环 | 移至文件顶部 |
| 异常处理过于宽泛 `except Exception` | `tray.py` `kill_port` 等函数 | 细化为具体异常类型，避免吞掉真实错误 |
| `start.ps1` 与 `tray.py` 重复实现端口清理逻辑 | `start.ps1` / `tray.py` | 统一入口：仅保留 `tray.py` 中的逻辑，`start.ps1` 改为直接调用 `tray.py` |

### 🟢 低优先级 / 架构优化

| 问题 | 改进方案 |
|------|----------|
| `server.py` 单文件混杂配置、数据库、路由逻辑 | 拆分为 `config.py` / `db.py` / `routes/` 分层结构（中期重构） |
| 用 `netstat` 字符串解析查找 PID（慢且脆弱）| 引入 `psutil` 替代：`pip install psutil`，速度快、跨平台 |
| 数据库 Schema 未配置 `ON DELETE CASCADE` | 修改 `gm_edges` 外键定义加 `ON DELETE CASCADE`，删节点时自动清理关联边 |
| 每次请求新建 SQLite 连接，无连接池 | 低并发场景可接受，中期考虑 SQLAlchemy 连接池 |
| VBS 启动强依赖 `uv` 在 PATH 中 | 增加 `uv` 存在性检查，不存在时回退到 `python` 直接启动 |

### 📋 改进执行顺序建议
1. 修复硬编码路径（影响跨机器使用，优先级最高）
2. 引入 `DbConnectionManager` 上下文管理器（防止 DB locked）
3. 修复删除节点的外键约束问题
4. 将 `import` 移至顶部 + 细化异常处理
5. 安装 `psutil` 替换 `netstat` 解析
6. 数据库 Schema 增加 `ON DELETE CASCADE`
7. 分层架构重构（长期）

---

## 已解决的历史问题

| 问题 | 解决时间 | 解决方案 |
|------|----------|----------|
| 前端文件结构损坏、乱码 | 2026-03-29 | 完全重写 `static/index.html` |
| 临时脚本堆积根目录 | 2026-03-29 | 清理 17 个临时文件和 frontend_parts/ 目录 |
| 图谱刷新后不显示 | 2026-03-29 | 清理 canvas.style.visibility hidden 残留代码 |
| 物理引擎抖动堆叠 | 2026-03-29 | 调整 iterations/gravitationalConstant/avoidOverlap |
| delete_node 重复执行 DELETE | 2026-03-29 | 删除冗余 SQL 语句 |
| create_edge DB locked 返回 500 | 2026-03-29 | 添加 try/except 友好降级 |
| 编辑节点面板按钮错误显示 | 2026-03-29 | toggleEditForm 控制按钮显隐 |
| 路径粘贴附带不可见字符 | 2026-03-29 | strip Unicode 方向控制字符 |
| reset-db 按钮调用错误 API | 2026-03-29 | 改调 /api/reset-db 接口 |
| 默认数据库路径不持久化 | 2026-03-29 | 写入 config.json，重启后保持 |
| 托盘图标不显示 | 2026-03-29 | 参考 gold-price 用 setup 回调 + icon.visible=True |
| VBScript 未结束的字符串常量 | 2026-03-29 | 用 Chr(34) 替代引号拼接 |
