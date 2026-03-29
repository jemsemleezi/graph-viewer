# Graph Viewer — 知识图谱可视化工具

一个基于 vis-network 的本地知识图谱浏览器，用以适配 https://github.com/adoresever/graph-memory 项目的知识图谱管理；
支持 SQLite 数据库和 JSON 文件，提供力导向图可视化、节点/关系增删改查、系统托盘快捷启动等功能；
并非openclaw或者其他agent的插件，只是一个脚本和前端管理器，随用随开，可以放在任何目录。

也支持其他知识图谱管理？可能，我没有测试


---

## 项目结构

```
graph-viewer/
├── static/
│   └── index.html      # 前端主文件（vis-network 力导向图）
├── server.py           # Flask 后端，提供 REST API
├── tray.py             # 系统托盘启动器
├── 启动图谱.vbs         # 双击启动入口（无黑色命令窗口）
├── start.ps1           # PowerShell 启动脚本（备用）
├── MEMO.md             # 开发备忘录
└── README.md           # 本文件
```

---

## 快速启动

### 方式一：双击启动（推荐）

双击 `启动图谱.vbs`，程序将：

1. 自动检测并清理占用 7892 端口的旧进程
2. 启动 Flask 服务器（`server.py`）
3. 在系统托盘显示图标
4. 自动打开浏览器访问 `http://127.0.0.1:7892`

> 托盘图标位于任务栏右下角，可能需要点击「^」展开隐藏图标。

### 方式二：命令行启动

```powershell
cd C:\Users\15967\.openclaw\workspace\projects\graph-viewer
uv run python tray.py
```

### 方式三：仅启动服务器（无托盘）

```powershell
uv run python server.py
```

---

## 托盘图标说明

| 操作 | 效果 |
|------|------|
| 左键单击 / 双击 | 打开浏览器访问图谱 |
| 右键 → 打开图谱 | 打开浏览器访问图谱 |
| 右键 → 退出 | 同步终止服务器并退出托盘 |

> 退出托盘图标时，服务器进程会被同步终止，无需手动关闭。

---

## 前端功能

### 图谱视图
- 力导向图展示，节点按类型着色
- 点击节点查看详情、编辑内容、删除节点
- 支持节点拖拽、缩放、平移
- 搜索框实时过滤节点
- 按类型筛选（SKILL / TASK / EVENT）

### 节点颜色
| 类型 | 颜色 |
|------|------|
| SKILL | 绿色 `#34d399` |
| TASK | 蓝色 `#60a5fa` |
| EVENT | 红色 `#f87171` |

### 关系颜色
| 类型 | 颜色 |
|------|------|
| USED_SKILL | 紫色 |
| SOLVED_BY | 橙色 |
| REQUIRES | 天蓝色 |
| PATCHES | 粉色 |
| CONFLICTS_WITH | 黄色 |

### 数据管理
- **新增节点**：填写名称、类型、描述、内容
- **新增关系**：指定起点、终点、关系类型
- **编辑节点**：点击节点 → 编辑节点按钮
- **删除节点**：点击节点 → 删除节点按钮（同步删除关联边）
- **表格视图**：切换为列表形式浏览所有节点，支持排序和搜索

### 数据源切换
- **默认数据库**：启动时自动连接配置的 SQLite 文件
- **切换数据库**：输入 `.db` 文件绝对路径后切换
- **载入 JSON**：上传符合格式的 JSON 文件
- **恢复默认**：一键恢复到默认数据库
- **设为默认**：将当前数据库持久化为默认（重启后保持）

---

## 后端 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/graph` | GET | 获取完整图谱数据 `{nodes, edges}` |
| `/api/node/<id>` | GET | 获取单个节点详情 |
| `/api/node` | POST | 新增节点 |
| `/api/node/<id>` | PUT | 更新节点 |
| `/api/node/<id>` | DELETE | 删除节点及关联边 |
| `/api/edge` | POST | 新增关系边 |
| `/api/edge/<id>` | DELETE | 删除关系边 |
| `/api/switch-db` | POST | 切换 SQLite 文件 `{"path": "..."}` |
| `/api/load-json` | POST | 载入 JSON 图谱 `{"nodes":[...],"edges":[...]}` |
| `/api/reset-db` | POST | 恢复默认数据库 |
| `/api/set-default-db` | POST | 将当前数据库设为默认 |

---

## 数据格式

### 节点（Node）
```json
{
  "id": "unique-id",
  "name": "节点名称",
  "type": "SKILL|TASK|EVENT",
  "description": "简短描述",
  "content": "详细内容（Markdown）",
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
  "instruction": "关系说明",
  "condition": "触发条件"
}
```

---

## 环境依赖

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)（包管理器）
- Flask
- pystray
- Pillow

依赖通过 `uv` 自动管理，无需手动 `pip install`。

---

## 访问地址

启动后浏览器访问：[http://127.0.0.1:7892](http://127.0.0.1:7892)
