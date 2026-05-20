import os

from app.config import Config


def write_script_file(name: str, content: str):
    """将脚本内容写入 scripts/ 目录。"""
    scripts_dir = Config.SCRIPTS_DIR
    os.makedirs(scripts_dir, exist_ok=True)
    path = os.path.join(scripts_dir, f"{name}.py")
    with open(path, "w") as f:
        f.write(content)


def remove_script_file(name: str):
    """从 scripts/ 目录删除脚本文件。"""
    path = os.path.join(Config.SCRIPTS_DIR, f"{name}.py")
    if os.path.exists(path):
        os.remove(path)
