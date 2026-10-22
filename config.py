# config.py
import argparse
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Config:
    vfs_path: Path = None
    startup_script: Path = None
    debug: bool = False

def parse_arguments() -> Config:
    parser = argparse.ArgumentParser(description="Эмулятор shell с VFS")
    parser.add_argument('--vfs', type=Path, help='Путь к ZIP-архиву VFS')
    parser.add_argument('--startup', type=Path, help='Путь к стартовому скрипту')
    parser.add_argument('--debug', action='store_true', help='Отладочный вывод')
    args = parser.parse_args()
    return Config(vfs_path=args.vfs, startup_script=args.startup, debug=args.debug)

def validate_config(cfg: Config) -> bool:
    if cfg.vfs_path and not cfg.vfs_path.exists():
        print(f"Ошибка: VFS-файл не найден: {cfg.vfs_path}")
        return False
    if cfg.startup_script and not cfg.startup_script.exists():
        print(f"Ошибка: стартовый скрипт не найден: {cfg.startup_script}")
        return False
    return True