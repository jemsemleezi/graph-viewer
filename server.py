#!/usr/bin/env python3
"""Graph Memory Viewer - Flask backend with safe node deletion (disable FK temporarily)"""
import sqlite3
import json
import os
import time
import uuid
import logging
from flask import Flask, jsonify, request, send_from_directory, after_this_request, send_file
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── 路径配置 ──
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
_BUILTIN_DEFAULT = os.path.join(os.path.expanduser('~'), '.openclaw', 'graph-memory.db')


def _load_config():
    if os.path.isfile(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_config(data):
    cfg = _load_config()
    cfg.update(data)
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


DEFAULT_DB_PATH = _load_config().get('default_db_path', _BUILTIN_DEFAULT)
_current_db_path = DEFAULT_DB_PATH
_json_graph = None


def get_db(path=None):
    p = path or _current_db_path
    for attempt in range(20):
        try:
            conn = sqlite3.connect(p, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        except sqlite3.OperationalError as e:
            if 'locked' in str(e) and attempt < 19:
                time.sleep(0.5)
                continue
            raise


# ── 升级表结构（统一 TEXT + CASCADE）──
def upgrade_edges_cascade(db_path):
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN TRANSACTION")

            fk_list = conn.execute("PRAGMA foreign_key_list(gm_edges)").fetchall()
            need_upgrade = True
            if fk_list:
                all_cascade = all(fk[6] == 'CASCADE' for fk in fk_list)
                if all_cascade:
                    need_upgrade = False

            if not need_upgrade:
                logger.info("gm_edges 表已支持 ON DELETE CASCADE，无需升级")
                conn.execute("COMMIT")
                conn.execute("PRAGMA foreign_keys = ON")
                return

            logger.warning("gm_edges 表缺少 ON DELETE CASCADE，开始升级...")
            conn.execute("ALTER TABLE gm_edges RENAME TO gm_edges_old")
            conn.execute("""
                CREATE TABLE gm_edges (
                    id TEXT PRIMARY KEY,
                    from_id TEXT,
                    to_id TEXT,
                    type TEXT,
                    instruction TEXT,
                    condition TEXT,
                    session_id TEXT,
                    created_at INTEGER,
                    FOREIGN KEY (from_id) REFERENCES gm_nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (to_id) REFERENCES gm_nodes(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO gm_edges (id, from_id, to_id, type, instruction, condition, session_id, created_at)
                SELECT 
                    id, 
                    CAST(from_id AS TEXT), 
                    CAST(to_id AS TEXT), 
                    type, 
                    instruction, 
                    condition, 
                    session_id, 
                    created_at
                FROM gm_edges_old
            """)
            conn.execute("DROP TABLE gm_edges_old")
            conn.execute("COMMIT")
            conn.execute("PRAGMA foreign_keys = ON")
            logger.info("升级完成，支持级联删除")
    except Exception as e:
        logger.error(f"升级失败: {e}")
        try:
            conn.execute("ROLLBACK")
        except:
            pass
        conn.execute("PRAGMA foreign_keys = ON")
        raise


def upgrade_current_db():
    if _json_graph is not None:
        return
    try:
        upgrade_edges_cascade(_current_db_path)
    except Exception as e:
        logger.error(f"升级失败: {e}")


# ── 错误处理 ──
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'not found', 'code': 404}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': str(e), 'code': 500}), 500


# ── 静态文件 ──
@app.route('/')
def index():
    resp = send_from_directory('static', 'index.html')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


# ── API 路由 ──
@app.route('/api/graph')
def get_graph():
    global _json_graph
    if _json_graph is not None:
        return jsonify(_json_graph)
    try:
        with get_db() as conn:
            nodes = conn.execute(
                "SELECT id, type, name, description, content, status, community_id, pagerank "
                "FROM gm_nodes WHERE status='active'"
            ).fetchall()
            edges = conn.execute(
                "SELECT id, from_id, to_id, type, instruction, condition FROM gm_edges"
            ).fetchall()
            return jsonify({
                'nodes': [dict(n) for n in nodes],
                'edges': [dict(e) for e in edges]
            })
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/switch-db', methods=['POST'])
def switch_db():
    global _current_db_path, _json_graph
    data = request.json or {}
    path = data.get('path', '').strip().strip('\u202a\u202b\u202c\u202d\u202e\u200b\ufeff')
    if not path:
        return jsonify({'error': '路径不能为空'}), 400
    if not os.path.isfile(path):
        return jsonify({'error': f'文件不存在: {path}'}), 400
    try:
        with sqlite3.connect(path) as conn:
            conn.execute("SELECT 1 FROM gm_nodes LIMIT 1")
    except sqlite3.OperationalError as e:
        return jsonify({'error': f'无法读取图谱数据: {str(e)}'}), 400
    _current_db_path = path
    _json_graph = None
    upgrade_current_db()
    return jsonify({'status': 'ok', 'path': path})


@app.route('/api/reset-db', methods=['POST'])
def reset_db():
    global _current_db_path, _json_graph
    _current_db_path = _load_config().get('default_db_path', _BUILTIN_DEFAULT)
    _json_graph = None
    upgrade_current_db()
    return jsonify({'status': 'ok', 'path': _current_db_path})


@app.route('/api/set-default-db', methods=['POST'])
def set_default_db():
    global DEFAULT_DB_PATH
    if _json_graph is not None:
        return jsonify({'error': '当前为 JSON 模式，无法设置为默认'}), 400
    if not _current_db_path:
        return jsonify({'error': '当前无活跃数据库'}), 400
    DEFAULT_DB_PATH = _current_db_path
    _save_config({'default_db_path': DEFAULT_DB_PATH})
    return jsonify({'status': 'ok', 'path': DEFAULT_DB_PATH})


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


@app.route('/api/source')
def get_source():
    if _json_graph is not None:
        return jsonify({'mode': 'json', 'nodes': len(_json_graph['nodes']), 'edges': len(_json_graph['edges'])})
    return jsonify({'mode': 'sqlite', 'path': _current_db_path})


@app.route('/api/current-db')
def current_db():
    return jsonify({'path': _current_db_path, 'is_json': _json_graph is not None})


@app.route('/api/node/<node_id>')
def get_node(node_id):
    if _json_graph is not None:
        node = next((n for n in _json_graph['nodes'] if n.get('id') == node_id), None)
        if not node:
            return jsonify({'error': 'not found'}), 404
        return jsonify(node)
    try:
        with get_db() as conn:
            node = conn.execute("SELECT * FROM gm_nodes WHERE id=?", (node_id,)).fetchone()
            if not node:
                return jsonify({'error': 'not found'}), 404
            return jsonify(dict(node))
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/node', methods=['POST'])
def create_node():
    if _json_graph is not None:
        return jsonify({'error': 'JSON 模式下不支持写入操作'}), 403
    data = request.json or {}
    node_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO gm_nodes "
                "(id, type, name, description, content, status, source_sessions, pagerank, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', '[]', 0, ?, ?)",
                (node_id, data.get('type', 'SKILL'), data.get('name', ''), data.get('description', ''),
                 data.get('content', ''), now, now)
            )
            return jsonify({'id': node_id, 'status': 'created'})
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/node/<node_id>', methods=['PUT'])
def update_node(node_id):
    if _json_graph is not None:
        return jsonify({'error': 'JSON模式不支持写操作'}), 403
    data = request.json or {}
    now = int(time.time() * 1000)
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE gm_nodes SET name=?, description=?, content=?, type=?, updated_at=? WHERE id=?",
                (data.get('name'), data.get('description'), data.get('content'), data.get('type'), now, node_id)
            )
            return jsonify({'status': 'updated'})
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/node/<node_id>', methods=['DELETE'])
def delete_node(node_id):
    if _json_graph is not None:
        return jsonify({'error': 'JSON模式下不支持写操作'}), 403
    try:
        with get_db() as conn:
            # 记录当前外键状态
            fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            app.logger.info(f"Deleting node {node_id}, foreign_keys={fk_status}")
            
            # 临时禁用外键约束
            conn.execute("PRAGMA foreign_keys=OFF")
            
            # 1. 删除所有关联边（使用 CAST 确保类型匹配）
            edge_del = conn.execute(
                "DELETE FROM gm_edges WHERE CAST(from_id AS TEXT) = ? OR CAST(to_id AS TEXT) = ?",
                (node_id, node_id)
            )
            app.logger.info(f"Deleted {edge_del.rowcount} edges")
            
            # 2. 手动清理 FTS 表中的引用（避免触发器报错）
            try:
                conn.execute(
                    "DELETE FROM gm_nodes_fts WHERE rowid IN (SELECT rowid FROM gm_nodes WHERE id = ?)",
                    (node_id,)
                )
            except Exception as e:
                app.logger.warning(f"FTS cleanup failed: {e}")
            
            # 3. 删除节点
            node_del = conn.execute("DELETE FROM gm_nodes WHERE id = ?", (node_id,))
            app.logger.info(f"Deleted {node_del.rowcount} nodes")
            
            # 重新启用外键约束
            conn.execute("PRAGMA foreign_keys=ON")
            
            if node_del.rowcount == 0:
                return jsonify({'error': '节点不存在'}), 404
            
            return jsonify({'status': 'deleted', 'edges_removed': edge_del.rowcount})
    except Exception as e:
        # 确保即使出错也重新启用外键（连接会关闭，但显式处理更好）
        app.logger.error(f"Delete node failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/edge', methods=['POST'])
def create_edge():
    if _json_graph is not None:
        return jsonify({'error': 'JSON 模式下不支持写入操作'}), 403
    data = request.json or {}
    edge_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO gm_edges "
                "(id, from_id, to_id, type, instruction, condition, session_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'manual', ?)",
                (edge_id, data['from_id'], data['to_id'], data.get('type', 'USED_SKILL'),
                 data.get('instruction', ''), data.get('condition', ''), now)
            )
            return jsonify({'id': edge_id, 'status': 'created'})
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/edge/<edge_id>', methods=['DELETE'])
def delete_edge(edge_id):
    if _json_graph is not None:
        return jsonify({'error': 'JSON模式下不支持写操作'}), 403
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM gm_edges WHERE id=?", (edge_id,))
            return jsonify({'status': 'deleted'})
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/edge/<edge_id>', methods=['PUT'])
def update_edge(edge_id):
    if _json_graph is not None:
        return jsonify({'error': 'JSON模式不支持写操作'}), 403
    data = request.json or {}
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE gm_edges SET type=?, instruction=?, condition=? WHERE id=?",
                (data.get('type', 'USED_SKILL'), data.get('instruction', ''), data.get('condition', ''), edge_id)
            )
            return jsonify({'status': 'updated'})
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


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
    try:
        with get_db() as conn:
            node_count = conn.execute("SELECT COUNT(*) FROM gm_nodes WHERE status='active'").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM gm_edges").fetchone()[0]
            community_count = conn.execute(
                "SELECT COUNT(DISTINCT community_id) FROM gm_nodes WHERE status='active' AND community_id IS NOT NULL"
            ).fetchone()[0]
            type_dist = conn.execute(
                "SELECT type, COUNT(*) as cnt FROM gm_nodes WHERE status='active' GROUP BY type"
            ).fetchall()
            return jsonify({
                'nodes': node_count,
                'edges': edge_count,
                'communities': community_count,
                'types': {row['type']: row['cnt'] for row in type_dist}
            })
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-sqlite')
def export_sqlite():
    import tempfile
    import shutil
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.db')
    os.close(tmp_fd)
    try:
        if _json_graph is not None:
            conn = sqlite3.connect(tmp_path)
            conn.execute('''CREATE TABLE IF NOT EXISTS gm_nodes (
                id TEXT PRIMARY KEY,
                type TEXT,
                name TEXT,
                description TEXT,
                content TEXT,
                status TEXT DEFAULT 'active',
                community_id INTEGER,
                pagerank REAL,
                created_at INTEGER,
                updated_at INTEGER)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS gm_edges (
                id TEXT PRIMARY KEY,
                from_id TEXT,
                to_id TEXT,
                type TEXT,
                instruction TEXT,
                condition TEXT,
                session_id TEXT,
                created_at INTEGER)''')
            for n in _json_graph.get('nodes', []):
                conn.execute("INSERT OR IGNORE INTO gm_nodes (id, type, name, description, content) VALUES (?, ?, ?, ?, ?)",
                             (n.get('id'), n.get('type'), n.get('name'), n.get('description'), n.get('content')))
            for e in _json_graph.get('edges', []):
                conn.execute("INSERT OR IGNORE INTO gm_edges (id, from_id, to_id, type, instruction, condition) VALUES (?, ?, ?, ?, ?, ?)",
                             (e.get('id'), e.get('from_id'), e.get('to_id'), e.get('type'), e.get('instruction'), e.get('condition')))
            conn.commit()
            conn.close()
        else:
            shutil.copyfile(_current_db_path, tmp_path)

        @after_this_request
        def cleanup(response):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return response

        return send_file(tmp_path, as_attachment=True, download_name='graph_memory_export.db')
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    upgrade_current_db()
    print(f'Graph Viewer running at http://127.0.0.1:7892')
    print(f'Default DB: {DEFAULT_DB_PATH}')
    app.run(host='127.0.0.1', port=7892, debug=False)