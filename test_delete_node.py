#!/usr/bin/env python3

import sqlite3
import sys
import os

def print_section(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def analyze_foreign_keys(conn, target_node_id):
    """分析所有引用 gm_nodes(id) 的外键约束"""
    print_section("外键约束分析")
    
    # 获取所有引用 gm_nodes 的外键
    fk_query = """
        SELECT 
            m.tbl_name as child_table,
            pti.name as child_column,
            fk."table" as parent_table,
            ptn.name as parent_column,
            fk."on_delete"
        FROM sqlite_master m
        JOIN pragma_foreign_key_list(m.tbl_name) fk ON fk.id = fk.id
        JOIN pragma_table_info(m.tbl_name) pti ON pti.cid = fk."from"
        JOIN pragma_table_info(fk."table") ptn ON ptn.cid = fk."to"
        WHERE m.type = 'table' AND fk."table" = 'gm_nodes'
        ORDER BY m.tbl_name
    """
    try:
        fk_rows = conn.execute(fk_query).fetchall()
        if not fk_rows:
            print("未找到引用 gm_nodes 的外键约束")
            return []
        
        print("引用 gm_nodes 的外键约束:")
        for row in fk_rows:
            print(f"  表 {row['child_table']}.{row['child_column']} -> {row['parent_table']}.{row['parent_column']}  ON DELETE {row['on_delete']}")
        return fk_rows
    except Exception as e:
        print(f"查询外键失败: {e}")
        return []

def check_references(conn, target_node_id, fk_constraints):
    """检查目标节点在各表中的引用数量"""
    print_section("节点引用计数")
    ref_counts = {}
    for fk in fk_constraints:
        child_table = fk['child_table']
        child_column = fk['child_column']
        try:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {child_table} WHERE CAST({child_column} AS TEXT) = ?",
                (target_node_id,)
            ).fetchone()[0]
            ref_counts[child_table] = count
            print(f"表 {child_table}.{child_column}: {count} 条引用")
        except Exception as e:
            print(f"检查表 {child_table} 失败: {e}")
            ref_counts[child_table] = -1
    return ref_counts

def try_delete_node(conn, target_node_id, strategy="normal"):
    """
    尝试删除节点
    strategy: 'normal' - 正常删除（先删边，再删节点）
              'disable_fk' - 临时禁用外键
              'cascade_manual' - 手动删除所有可能的引用行
    """
    print_section(f"尝试删除策略: {strategy}")
    try:
        if strategy == "normal":
            # 先删边
            conn.execute(
                "DELETE FROM gm_edges WHERE CAST(from_id AS TEXT) = ? OR CAST(to_id AS TEXT) = ?",
                (target_node_id, target_node_id)
            )
            print(f"已删除边数量: {conn.total_changes}")
            # 再删节点
            conn.execute("DELETE FROM gm_nodes WHERE id = ?", (target_node_id,))
            deleted = conn.total_changes
            print(f"删除节点结果: {deleted} 行")
            return deleted > 0
        
        elif strategy == "disable_fk":
            # 先删边
            conn.execute(
                "DELETE FROM gm_edges WHERE CAST(from_id AS TEXT) = ? OR CAST(to_id AS TEXT) = ?",
                (target_node_id, target_node_id)
            )
            print(f"已删除边数量: {conn.total_changes}")
            # 临时禁用外键
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("DELETE FROM gm_nodes WHERE id = ?", (target_node_id,))
            deleted = conn.total_changes
            conn.execute("PRAGMA foreign_keys=ON")
            print(f"删除节点结果: {deleted} 行")
            return deleted > 0
        
        elif strategy == "cascade_manual":
            # 查找所有引用该节点的表并手动删除
            fk_constraints = analyze_foreign_keys(conn, target_node_id)
            for fk in fk_constraints:
                child_table = fk['child_table']
                child_column = fk['child_column']
                # 删除所有引用行
                conn.execute(
                    f"DELETE FROM {child_table} WHERE CAST({child_column} AS TEXT) = ?",
                    (target_node_id,)
                )
                print(f"从 {child_table} 删除了 {conn.total_changes} 行")
            # 最后删节点
            conn.execute("DELETE FROM gm_nodes WHERE id = ?", (target_node_id,))
            deleted = conn.total_changes
            print(f"删除节点结果: {deleted} 行")
            return deleted > 0
        
        else:
            print("未知策略")
            return False
    except sqlite3.Error as e:
        print(f"SQLite 错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("用法: python test_delete_node.py <数据库路径>")
        sys.exit(1)
    
    db_path = sys.argv[1].strip()
    if not os.path.isfile(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)
    
    target_node_id = "n-1774366318682-wysd1"
    print(f"目标节点ID: {target_node_id}")
    print(f"数据库路径: {db_path}")
    
    try:
        # 连接数据库（不自动开启外键，以便测试不同策略）
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        print("数据库连接成功")
        
        # 1. 检查节点是否存在
        node = conn.execute("SELECT * FROM gm_nodes WHERE id = ?", (target_node_id,)).fetchone()
        if node:
            print(f"节点存在: {dict(node)}")
        else:
            print("节点不存在，退出")
            conn.close()
            return
        
        # 2. 分析外键约束
        fk_constraints = analyze_foreign_keys(conn, target_node_id)
        
        # 3. 检查引用计数
        ref_counts = check_references(conn, target_node_id, fk_constraints)
        
        # 4. 尝试各种删除策略
        strategies = ["normal", "disable_fk", "cascade_manual"]
        success = False
        for strat in strategies:
            # 回滚到初始状态（为了测试，每次重新连接）
            conn.close()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            # 重新检查节点是否存在（避免之前删除）
            node_exists = conn.execute("SELECT 1 FROM gm_nodes WHERE id = ?", (target_node_id,)).fetchone()
            if not node_exists:
                print("节点已被之前的策略删除，终止测试")
                break
            
            if try_delete_node(conn, target_node_id, strat):
                success = True
                print(f"✅ 策略 '{strat}' 成功删除节点")
                # 验证是否真的删除
                after = conn.execute("SELECT 1 FROM gm_nodes WHERE id = ?", (target_node_id,)).fetchone()
                if not after:
                    print("验证: 节点已彻底删除")
                else:
                    print("验证: 节点仍然存在？")
                break
            else:
                print(f"❌ 策略 '{strat}' 失败")
        
        if not success:
            print("\n所有策略均失败，请手动检查数据库外键定义和触发器。")
        
        # 5. 检查是否还有其他触发器或视图
        print_section("数据库触发器")
        triggers = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'").fetchall()
        for t in triggers:
            print(f"触发器 {t['name']}: {t['sql']}")
        
        conn.close()
        
    except Exception as e:
        print(f"程序异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()