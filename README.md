# Graph Viewer — 知识图谱可视化工具

一个基于 vis-network 的本地知识图谱浏览器，用以适配 [graph-memory](https://github.com/adoresever/graph-memory) 项目的知识图谱管理。

支持 SQLite 数据库和 JSON 文件，提供力导向图可视化、节点/关系增删改查、系统托盘快捷启动等功能。

> **定位说明**：并非 openclaw 或者其他 agent 的插件，只是一个纯粹的本地脚本和前端管理器，随用随开，可以放在任何目录。

---

## 项目结构

```
graph-viewer/
├── static/
│   └── index.html      # 前端主文件（vis-network 力导向图）
├── server.py           # Flask 后端，提供 REST API
├── tray.py             # 系统托盘启停控制脚本
├── 启动图谱.vbs        # 双击启动入口（无黑色命令窗口）
├── start.ps1           # PowerShell 启动脚本（备用，自动清端口）
├── pyproject.toml      # 依赖管理配置（实现零配置启动的核心）
├── config.json         # 运行时自动生成的默认数据库持久化配置
└── README.md           # 本文件
```


---

## 快速启动（零配置）

得益于 `pyproject.toml` 和 `uv` 包管理器，**无需手动执行 `pip install`**。

### 方式一：双击启动（推荐）
直接双击 `启动图谱.vbs`，程序将自动完成以下动作：
1. `uv` 检测依赖并自动创建虚拟环境（首次运行时）
2. `uv` 自动安装 Flask、pystray 等所需依赖
3. 自动检测并清理占用 7892 端口的旧进程
4. 后台启动 Flask 服务器（`server.py`）
5. 在系统托盘显示图标，并自动打开浏览器访问 `http://127.0.0.1:7892`

> 💡 托盘图标位于任务栏右下角，可能需要点击「^」展开隐藏图标才能看到。

### 方式二：命令行启动

```powershell
cd /path/to/graph-viewer
uv run python tray.py
```

### 方式三：仅启动服务器（无托盘，用于调试）

```powershell
uv run python server.py
```

---

## 托盘图标说明

| 操作 | 效果 |
|------|------|
| 左键单击 / 双击 | 打开浏览器访问图谱 |
| 右键 → 打开图谱 | 打开浏览器访问图谱 |
| 右键 → 退出 | **同步终止服务器进程**并退出托盘 |

> 退出托盘图标时，后台服务会被彻底 kill，无需打开任务管理器手动清理。

---

## 前端功能与交互

### 图谱视图
- **力导向图展示**：节点按类型自动着色，大小随权重（pagerank）动态缩放
- **高性能筛选**：支持上千节点场景下的实时搜索与类型过滤（底层使用原生 hidden 属性优化，不卡顿）
- **无感刷新**：定时刷新或手动重载时，自动保持当前的视图缩放与焦点位置，不闪屏
- **交互操作**：支持节点拖拽、画布缩放、平移

### 节点颜色规范
| 类型 | 颜色 | 色值 |
|------|------|------|
| SKILL (技能) | 蓝色 | `#4f8cff` |
| TASK (任务) | 绿色 | `#34d399` |
| EVENT (事件) | 黄色 | `#fbbf24` |

### 关系颜色规范
| 类型 | 颜色 | 色值 |
|------|------|------|
| USED_SKILL (使用技能) | 浅蓝 | `#60a5fa` |
| SOLVED_BY (被解决) | 绿色 | `#34d399` |
| REQUIRES (依赖于) | 紫色 | `#a78bfa` |
| PATCHES (修补) | 黄色 | `#fbbf24` |
| CONFLICTS_WITH (冲突) | 红色 | `#f87171` |

### 数据管理
- **新增节点/关系**：通过顶部菜单栏操作，关系支持模糊搜索选择节点
- **编辑/删除**：点击节点或边，在右侧滑出详情面板中进行操作
- **智能错误提示**：如在“JSON内存模式”下误操作写入，会拦截并引导用户切换回 SQLite
- **表格视图**：切换为列表形式浏览所有节点/边数据

### 数据源切换
- **默认数据库**：启动时自动连接 `~/.openclaw/graph-memory.db`
- **切换数据库**：输入 `.db` 文件绝对路径切换（自动处理 Windows 不可见字符及反斜杠转义）
- **载入 JSON**：上传符合格式的 JSON 文件进入纯内存模式（关闭写操作）
- **恢复默认**：一键恢复到默认数据库路径
- **设为默认**：将当前连接的数据库路径持久化到 `config.json`

---

## 后端 API 接口

### 节点管理
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/node/<id>` | GET | 获取单个节点详情 |
| `/api/node` | POST | 新增节点 |
| `/api/node/<id>` | PUT | 更新节点 |
| `/api/node/<id>` | DELETE | 删除节点及关联边（自动处理外键与FTS索引） |

### 关系管理
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/edge` | POST | 新增关系边 |
| `/api/edge/<id>` | PUT | 更新关系属性 |
| `/api/edge/<id>` | DELETE | 删除关系边 |

### 数据源与视图
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/graph` | GET | 获取完整图谱数据 `{nodes, edges}` |
| `/api/stats` | GET | 获取统计信息（节点数、边数、类型分布） |
| `/api/source` | GET | 获取当前数据源模式（sqlite/json） |
| `/api/switch-db` | POST | 切换 SQLite 文件 `{"path": "..."}` |
| `/api/load-json` | POST | 载入 JSON 图谱 `{"nodes":[...],"edges":[...]}` |
| `/api/reset-db` | POST | 恢复默认数据库 |
| `/api/set-default-db` | POST | 将当前数据库路径持久化配置 |
| `/api/export-sqlite` | GET | 将当前图谱导出为 `.db` 文件下载 |

---

## 数据格式规范

### 节点（Node）
```json
{
  "id": "unique-id",
  "name": "节点名称",
  "type": "SKILL|TASK|EVENT",
  "description": "简短描述",
  "content": "详细内容（支持纯文本/Markdown）",
  "pagerank": 0.0,
  "community_id": "c-1",
  "status": "active"
}
```

### 边（Edge）
```json
{
  "id": "unique-id",
  "from_id": "节点A的id",
  "to_id": "节点B的id",
  "type": "USED_SKILL|SOLVED_BY|REQUIRES|PATCHES|CONFLICTS_WITH",
  "instruction": "关系说明/执行指令",
  "condition": "触发条件"
}
```

---


---

## 环境依赖

本项目的 Python 依赖**完全由 `pyproject.toml` 管理**，包含但不限于：
- Flask & flask-cors
- pystray & Pillow
- psutil

**前置要求**：
- [Python 3.10+](https://www.python.org/downloads/)
- [uv 包管理器](https://github.com/astral-sh/uv) （安装极简：`pip install uv` 或 `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`）

> 只要装好了 `uv`，剩下的交给 `启动图谱.vbs` 即可，不用管虚拟环境和 pip。

---

## 访问地址
启动成功后，浏览器自动访问：[http://127.0.0.1:7892](http://127.0.0.1:7892)

