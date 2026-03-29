#!/usr/bin/env python3
"""Graph Memory Viewer - Flask backend"""
import sqlite3
import json
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder='static')
CORS(app)

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def _load_config():
    if os.path.isfile(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_config(data):
    cfg = _load_config()
    cfg.update(data)
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

_BUILTIN_DEFAULT = r'C:\Users\15967\.openclaw\graph-memory.db'
DEFAULT_DB_PATH = _load_config().get('default_db_path', _BUILTIN_DEFAULT)

# 当前使用的 DB 路径（可被 /api/switch-db 切换）
_current_db_path = DEFAULT_DB_PATH
# 内存中的 JSON 图谱数据（当用户上传 JSON 时使用，优先于 SQLite）
_json_graph = None  # {'nodes': [...], 'edges': [...]}


def get_db(path=None):
    import time
    p = path or _current_db_path
    for attempt in range(20):
        try:
            conn = sqlite3.connect(p, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            return conn
        except sqlite3.OperationalError as e:
            if 'locked' in str(e) and attempt < 19:
                time.sleep(0.5)
                continue
            raise


# ── 静态文件 ──
@app.route('/')
def index():
    resp = send_from_directory('static', 'index.html')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


# ── 读取图谱数据 ──
@app.route('/api/graph')
def get_graph():
    global _json_graph
    if _json_graph is not None:
        return jsonify(_json_graph)
    conn = get_db()
    nodes = conn.execute(
        "SELECT id, type, name, description, content, status, community_id, pagerank FROM gm_nodes WHERE status='active'"
    ).fetchall()
    edges = conn.execute(
        "SELECT id, from_id, to_id, type, instruction, condition FROM gm_edges"
    ).fetchall()
    conn.close()
    return jsonify({
        'nodes': [dict(n) for n in nodes],
        'edges': [dict(e) for e in edges]
    })


# ── 切换 SQLite 路径 ──
@app.route('/api/switch-db', methods=['POST'])
def switch_db():
    global _current_db_path, _json_graph
    data = request.json or {}
    # 去除首尾空白及常见 Unicode 方向控制字符（如从文件管理器复制路径时附带的 U+202A 等）
    path = data.get('path', '').strip().strip('\u202a\u202b\u202c\u202d\u202e\u200b\ufeff')
    if not path:
        return jsonify({'error': '路径不能为空'}), 400
    if not os.path.isfile(path):
        return jsonify({'error': f'文件不存在: {path}'}), 400
    # 尝试连接验证
    try:
        conn = sqlite3.connect(path)
        conn.execute("SELECT 1 FROM gm_nodes LIMIT 1")
        conn.close()
    except Exception as e:
        return jsonify({'error': f'无法读取图谱数据: {str(e)}'}), 400
    _current_db_path = path
    _json_graph = None  # 清除 JSON 模式
    return jsonify({'status': 'ok', 'path': path})


# ── 恢复默认 DB ──
@app.route('/api/reset-db', methods=['POST'])
def reset_db():
    global _current_db_path, _json_graph
    _current_db_path = _load_config().get("default_db_path", _BUILTIN_DEFAULT)
    _json_graph = None
    return jsonify({'status': 'ok', 'path': _current_db_path})


@app.route('/api/set-default-db', methods=['POST'])
def set_default_db():
    global DEFAULT_DB_PATH
    if _json_graph is not None:
        return jsonify({'error': '当前为 JSON 模式，无法设置为默认'}), 400
    if not _current_db_path:
        return jsonify({'error': '当前无活跃数据库'}), 400
    DEFAULT_DB_PATH = _current_db_path
    _save_config({"default_db_path": DEFAULT_DB_PATH})
    return jsonify({'status': 'ok', 'path': DEFAULT_DB_PATH})


# ── 加载 JSON 图谱 ──
@app.route('/api/load-json', methods=['POST'])
def load_json():
    global _json_graph
    data = request.json
    if not data:
        return jsonify({'error': '请求体为空'}), 400
    nodes = data.get('nodes')
    edges = data.get('edges')
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return jsonify({'error': 'JSON 格式错误，需含 nodes 和 edges 数组'}), 400
    _json_graph = {'nodes': nodes, 'edges': edges}
    return jsonify({'status': 'ok', 'nodes': len(nodes), 'edges': len(edges)})


# ── 当前数据源信息 ──
@app.route('/api/source')
def get_source():
    if _json_graph is not None:
        return jsonify({'mode': 'json', 'nodes': len(_json_graph['nodes']), 'edges': len(_json_graph['edges'])})
    return jsonify({'mode': 'sqlite', 'path': _current_db_path})


# ── 获取单个节点详情 ──
@app.route('/api/node/<node_id>')
def get_node(node_id):
    if _json_graph is not None:
        node = next((n for n in _json_graph['nodes'] if n.get('id') == node_id), None)
        if not node:
            return jsonify({'error': 'not found'}), 404
        return jsonify(node)
    conn = get_db()
    node = conn.execute(
        "SELECT * FROM gm_nodes WHERE id=?", (node_id,)
    ).fetchone()
    conn.close()
    if not node:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(node))


# ── 新增节点 ──
@app.route('/api/node', methods=['POST'])
def create_node():
    if _json_graph is not None:
        return jsonify({'error': 'JSON 模式下不支持写入操作'}), 403
    data = request.json
    import time, uuid
    node_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    conn = get_db()
    conn.execute(
        "INSERT INTO gm_nodes (id, type, name, description, content, status, source_sessions, pagerank, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 'active', '[]', 0, ?, ?)",
        (node_id, data.get('type', 'SKILL'), data.get('name', ''), data.get('description', ''), data.get('content', ''), now, now)
    )
    conn.commit()
    conn.close()
    return jsonify({'id': node_id, 'status': 'created'})


# ── 修改节点 ──
@app.route('/api/node/<node_id>', methods=['PUT'])
def update_node(node_id):
    if _json_graph is not None:
        return jsonify({'error': 'JSON模式不支持写操作'}), 403
    data = request.json
    import time
    now = int(time.time() * 1000)
    try:
        conn = get_db()
        conn.execute(
            "UPDATE gm_nodes SET name=?, description=?, content=?, type=?, updated_at=? WHERE id=?",
            (data.get('name'), data.get('description'), data.get('content'), data.get('type'), now, node_id)
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ── 删除节点（软删除） ──
@app.route('/api/node/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    if _json_graph is not None:
        return jsonify({'error': 'JSON模式下不支持写操作'}), 403
    try:
        conn = get_db()
        conn.execute("PRAGMA foreign_keys=OFF")
        # 先删关联边（避免外键约束）
        conn.execute("DELETE FROM gm_edges WHERE from_id=? OR to_id=?", (node_id, node_id))
        conn.execute("DELETE FROM gm_nodes WHERE id=?", (node_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'deleted'})
    except Exception as e:
        err = str(e)
        if 'locked' in err:
            return jsonify({'status': 'frontend_only', 'warning': 'DB被占用，已仅移除前端显示'}), 200
        return jsonify({'error': err}), 500

# ── 新增边 ──
@app.route('/api/edge', methods=['POST'])
def create_edge():
    if _json_graph is not None:
        return jsonify({'error': 'JSON 模式下不支持写入操作'}), 403
    data = request.json
    import uuid
    import time
    edge_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO gm_edges (id, from_id, to_id, type, instruction, condition, session_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'manual', ?)",
            (edge_id, data['from_id'], data['to_id'], data.get('type', 'USED_SKILL'), data.get('instruction', ''), data.get('condition', ''), now)
        )
        conn.commit()
        conn.close()
        return jsonify({'id': edge_id, 'status': 'created'})
    except Exception as e:
        err = str(e)
        if 'locked' in err:
            return jsonify({'status': 'frontend_only', 'warning': 'DB被占用，已仅记录前端显示'}), 200
        return jsonify({'error': err}), 500


# ── 删除边 ──
@app.route('/api/edge/<edge_id>', methods=['DELETE'])
def delete_edge(edge_id):
    if _json_graph is not None:
        return jsonify({'error': 'JSON模式下不支持写操作'}), 403
    try:
        conn = get_db()
        conn.execute("DELETE FROM gm_edges WHERE id=?", (edge_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'deleted'})
    except Exception as e:
        err = str(e)
        if 'locked' in err:
            return jsonify({'status': 'frontend_only', 'warning': 'DB被占用，已仅移除前端显示'}), 200
        return jsonify({'error': err}), 500

# ── 统计 ──

@app.route('/api/current-db')
def current_db():
    return jsonify({'path': _current_db_path, 'is_json': _json_graph is not None})
@app.route('/api/stats')
def get_stats():
    if _json_graph is not None:
        nodes = _json_graph['nodes']
        edges = _json_graph['edges']
        type_dist = {}
        for n in nodes:
            t = n.get('type', 'UNKNOWN')
            type_dist[t] = type_dist.get(t, 0) + 1
        communities = set(n.get('community_id') for n in nodes if n.get('community_id'))
        return jsonify({
            'nodes': len(nodes),
            'edges': len(edges),
            'communities': len(communities),
            'types': type_dist
        })
    conn = get_db()
    node_count = conn.execute("SELECT COUNT(*) FROM gm_nodes WHERE status='active'").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM gm_edges").fetchone()[0]
    community_count = conn.execute("SELECT COUNT(DISTINCT community_id) FROM gm_nodes WHERE status='active' AND community_id IS NOT NULL").fetchone()[0]
    type_dist = conn.execute("SELECT type, COUNT(*) as cnt FROM gm_nodes WHERE status='active' GROUP BY type").fetchall()
    conn.close()
    return jsonify({
        'nodes': node_count,
        'edges': edge_count,
        'communities': community_count,
        'types': {row['type']: row['cnt'] for row in type_dist}
    })


if __name__ == '__main__':
    print('Graph Viewer running at http://127.0.0.1:7892')
    app.run(host='127.0.0.1', port=7892, debug=False)
