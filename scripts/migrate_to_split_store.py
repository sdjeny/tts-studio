#!/usr/bin/env python3
"""
迁移脚本：将单文件 studio.json 拆分为多文件项目存储。

工作流程（migrate）：
1. 读取 data/studio.json
2. 为每个项目创建 data/projects/{id}.json
3. 生成 data/projects_index.json
4. 备份 studio.json → studio.json.bak
5. 删除 studio.json

回滚流程（rollback）：
1. 检查 studio.json.bak 是否存在
2. 从 projects/*.json 重建 studio.json（保持各项目最新状态）
3. 或直接从 studio.json.bak 恢复
"""

import json
import os
import shutil
import sys
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STUDIO_JSON = DATA_DIR / "studio.json"
STUDIO_BAK = DATA_DIR / "studio.json.bak"
PROJECTS_DIR = DATA_DIR / "projects"
INDEX_FILE = DATA_DIR / "projects_index.json"


# ── 辅助 ──────────────────────────────────────────────────────
def _project_path(project_id: str) -> Path:
    return PROJECTS_DIR / f"{project_id}.json"


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ── 迁移 ──────────────────────────────────────────────────────
def migrate() -> None:
    """将 studio.json 拆分为 projects/{id}.json + projects_index.json。"""
    if not STUDIO_JSON.exists():
        print("❌ studio.json 不存在，无需迁移。")
        return

    print(f"📂 读取 {STUDIO_JSON}")
    with open(STUDIO_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    projects = data.get("projects", [])
    if not projects:
        print("⚠️  studio.json 中没有项目，跳过。")
        return

    print(f"📦 发现 {len(projects)} 个项目")

    # 确保 projects 目录存在
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    index_entries = []

    for p in projects:
        pid = p.get("id")
        if not pid:
            print(f"  ⚠️  跳过无 id 的项目: {p.get('name', '<unknown>')}")
            continue

        # 写入单个项目文件
        path = _project_path(pid)
        tmp = str(path) + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(path))
            print(f"  ✅ 写入 {path.name}")
        except Exception as e:
            print(f"  ❌ 写入 {path.name} 失败: {e}")
            try:
                os.remove(tmp)
            except OSError:
                pass
            continue

        # 收集索引条目
        index_entries.append({
            "id": pid,
            "name": p.get("name", ""),
            "updated_at": p.get("updated_at", p.get("created_at", "")),
        })

    # 写入索引
    index_data = {
        "version": 1,
        "projects": index_entries,
    }
    tmp_idx = str(INDEX_FILE) + ".tmp"
    try:
        with open(tmp_idx, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_idx, str(INDEX_FILE))
        print(f"  ✅ 索引写入 {INDEX_FILE.name}（共 {len(index_entries)} 条）")
    except Exception as e:
        print(f"  ❌ 索引写入失败: {e}")
        try:
            os.remove(tmp_idx)
        except OSError:
            pass
        return

    # 备份旧文件
    try:
        shutil.copy2(str(STUDIO_JSON), str(STUDIO_BAK))
        print(f"  ✅ 备份 {STUDIO_JSON.name} → {STUDIO_BAK.name}")
    except Exception as e:
        print(f"  ⚠️  备份失败: {e}")

    # 删除旧文件
    try:
        STUDIO_JSON.unlink()
        print(f"  ✅ 删除 {STUDIO_JSON.name}")
    except Exception as e:
        print(f"  ⚠️  删除 {STUDIO_JSON.name} 失败: {e}")

    print(f"\n🎉 迁移完成！{len(projects)} 个项目已拆分。")
    print(f"   - 项目文件: {PROJECTS_DIR}/")
    print(f"   - 索引文件: {INDEX_FILE}")
    print(f"   - 旧文件备份: {STUDIO_BAK}")


# ── 回滚 ──────────────────────────────────────────────────────
def rollback() -> None:
    """从 projects/*.json 重建 studio.json。"""
    if not PROJECTS_DIR.exists():
        print("❌ projects/ 目录不存在，无法回滚。")
        return

    project_files = sorted(PROJECTS_DIR.glob("*.json"))
    if not project_files:
        print("⚠️  projects/ 下没有项目文件。")

    projects = []
    for pf in project_files:
        try:
            with open(pf, "r", encoding="utf-8") as f:
                projects.append(json.load(f))
        except Exception as e:
            print(f"  ⚠️  读取 {pf.name} 失败: {e}")

    # 重建 studio.json
    data = {"projects": projects}
    tmp = str(STUDIO_JSON) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(STUDIO_JSON))
        print(f"  ✅ 重建 {STUDIO_JSON.name}（共 {len(projects)} 个项目）")
    except Exception as e:
        print(f"  ❌ 重建 {STUDIO_JSON.name} 失败: {e}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return

    # 删除索引和项目文件
    try:
        INDEX_FILE.unlink(missing_ok=True)
        print(f"  ✅ 删除索引 {INDEX_FILE.name}")
    except Exception as e:
        print(f"  ⚠️  删除索引失败: {e}")

    try:
        shutil.rmtree(str(PROJECTS_DIR))
        print(f"  ✅ 删除 projects/ 目录")
    except Exception as e:
        print(f"  ⚠️  删除 projects/ 失败: {e}")

    print(f"\n🎉 回滚完成！已恢复为单文件存储。")


# ── 验证 ──────────────────────────────────────────────────────
def verify() -> bool:
    """验证迁移后数据完整性。"""
    if not INDEX_FILE.exists():
        print("❌ 索引文件不存在")
        return False

    # 加载索引
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        idx = json.load(f)

    errors = 0
    for entry in idx.get("projects", []):
        pid = entry["id"]
        pp = _project_path(pid)
        if not pp.exists():
            print(f"  ❌ 项目文件缺失: {pp.name}")
            errors += 1
            continue
        try:
            with open(pp, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            if pdata.get("id") != pid:
                print(f"  ❌ 项目 ID 不匹配: {pp.name}")
                errors += 1
            if pdata.get("name") != entry.get("name"):
                print(f"  ⚠️  项目名不一致: {pp.name}")
        except Exception as e:
            print(f"  ❌ 读取 {pp.name} 失败: {e}")
            errors += 1

    total = len(idx.get("projects", []))
    if errors == 0:
        print(f"✅ 验证通过！{total} 个项目完整性检查全部通过。")
    else:
        print(f"⚠️  验证完成，{total} 个项目中 {errors} 个有问题。")
    return errors == 0


# ── 入口 ──────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("用法: python -m scripts.migrate_to_split_store [migrate|rollback|verify]")
        sys.exit(1)

    command = sys.argv[1].lower()
    if command == "migrate":
        migrate()
    elif command == "rollback":
        rollback()
    elif command == "verify":
        sys.exit(0 if verify() else 1)
    else:
        print(f"未知命令: {command}")
        print("可用命令: migrate, rollback, verify")
        sys.exit(1)


if __name__ == "__main__":
    main()