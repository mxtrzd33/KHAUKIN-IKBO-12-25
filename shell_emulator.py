#!/usr/bin/env python3
# shell_emulator.py
import getpass
import socket
import shlex
import sys
import os
from typing import List, Optional
from config import Config, parse_arguments, validate_config
from vfs import VirtualFileSystem

class ShellEmulator:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.running = True
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.vfs = VirtualFileSystem()
        self.vfs_loaded = False

        if cfg.vfs_path:
            self.vfs_loaded = self.vfs.load_from_zip(cfg.vfs_path)

        # Регистрация команд
        self.commands = {
            'ls': self.cmd_ls,
            'cd': self.cmd_cd,
            'pwd': self.cmd_pwd,
            'cat': self.cmd_cat,
            'find': self.cmd_find,
            'tree': self.cmd_tree,
            'uname': self.cmd_uname,
            'du': self.cmd_du,
            'rev': self.cmd_rev,
            'touch': self.cmd_touch,
            'mv': self.cmd_mv,
            'rm': self.cmd_rm,
            'vfs-save': self.cmd_vfs_save,
            'vfs-info': self.cmd_vfs_info,
            'exit': self.cmd_exit,
        }

    def get_prompt(self) -> str:
        if self.vfs_loaded:
            path = self.vfs.get_current_path()
        else:
            path = "~"
        return f"{self.username}@{self.hostname}:{path}$ "

    def parse_command(self, line: str):
        try:
            tokens = shlex.split(line)
            if not tokens:
                return None, []
            return tokens[0], tokens[1:]
        except ValueError as e:
            print(f"Ошибка парсинга: {e}")
            return None, []

    def execute(self, cmd: str, args: List[str]):
        if cmd in self.commands:
            try:
                self.commands[cmd](args)
            except Exception as e:
                print(f"Ошибка выполнения '{cmd}': {e}")
                if self.cfg.debug:
                    import traceback
                    traceback.print_exc()
        else:
            print(f"Ошибка: команда не найдена: {cmd}")

    # ---------- команды Этап 4 ----------
    def cmd_ls(self, args):
        if not self.vfs_loaded:
            print("ls: VFS не загружена"); return
        show_all, long_fmt, paths = False, False, []
        for a in args:
            if a.startswith('-'):
                if 'a' in a: show_all = True
                if 'l' in a: long_fmt = True
            else:
                paths.append(a)
        if not paths: paths = ['']
        for p in paths:
            lines = self.vfs.list_directory(p, show_all, long_fmt)
            for ln in lines: print(ln)

    def cmd_cd(self, args):
        if not self.vfs_loaded:
            print("cd: VFS не загружена"); return
        if len(args) == 0:
            self.vfs.change_directory('/')
        elif len(args) == 1:
            self.vfs.change_directory(args[0])
        else:
            print("cd: слишком много аргументов")

    def cmd_pwd(self, args):
        if self.vfs_loaded:
            print(self.vfs.get_current_path())
        else:
            print("~")

    def cmd_cat(self, args):
        if not self.vfs_loaded:
            print("cat: VFS не загружена"); return
        if not args:
            print("cat: отсутствует операнд"); return
        for p in args:
            self.vfs.cat(p)

    def cmd_find(self, args):
        if not self.vfs_loaded:
            print("find: VFS не загружена"); return
        if not args:
            print("find: укажите шаблон"); return
        res = self.vfs.find(args[0])
        if res:
            print("\n".join(res))
        else:
            print(f"find: '{args[0]}' не найдено")

    def cmd_tree(self, args):
        if not self.vfs_loaded:
            print("tree: VFS не загружена"); return
        def walk(node, prefix=""):
            items = sorted(node.children.values(), key=lambda n: n.name)
            for i, ch in enumerate(items):
                last = i == len(items) - 1
                print(prefix + ("└── " if last else "├── ") + ch.name)
                if ch.is_dir:
                    walk(ch, prefix + ("    " if last else "│   "))
        print(self.vfs.get_current_path())
        walk(self.vfs.cwd)

    def cmd_uname(self, args):
        # Этап 4: вывод информации о системе
        if '-a' in args:
            print(f"Linux {self.hostname} 5.15.0-emu #1 SMP {self.username}")
        else:
            print("Linux")

    def cmd_du(self, args):
        # Этап 4: оценка размера директории
        if not self.vfs_loaded:
            print("du: VFS не загружена"); return
        path = args[0] if args else '.'
        node = self.vfs._resolve(path)
        if node is None:
            print(f"du: cannot access '{path}'"); return
        total = 0
        def calc(n):
            nonlocal total
            for ch in n.children.values():
                if ch.is_dir:
                    calc(ch)
                else:
                    total += len(ch.content)
        if node.is_dir:
            calc(node)
        else:
            total = len(node.content)
        print(f"{total}\t{path}")

    def cmd_rev(self, args):
        # Этап 4: переворот строк
        if not args:
            print("rev: отсутствует аргумент"); return
        if self.vfs_loaded and args[0] in [n.name for n in self.vfs.cwd.children.values()]:
            node = self.vfs._resolve(args[0])
            if node and not node.is_dir:
                try:
                    text = node.content.decode('utf-8')
                    for line in text.splitlines():
                        print(line[::-1])
                except UnicodeDecodeError:
                    print("rev: бинарный файл")
                return
        print(args[0][::-1])

    # ---------- команды Этап 5 ----------
    def cmd_touch(self, args):
        if not self.vfs_loaded:
            print("touch: VFS не загружена"); return
        if not args:
            print("touch: отсутствует операнд"); return
        for p in args:
            self.vfs.touch(p)

    def cmd_mv(self, args):
        if not self.vfs_loaded:
            print("mv: VFS не загружена"); return
        if len(args) != 2:
            print("mv: требуется источник и назначение"); return
        self.vfs.move(args[0], args[1])

    def cmd_rm(self, args):
        if not self.vfs_loaded:
            print("rm: VFS не загружена"); return
        recursive, force, paths = False, False, []
        for a in args:
            if a.startswith('-'):
                if 'r' in a or 'R' in a: recursive = True
                if 'f' in a: force = True
            else:
                paths.append(a)
        if not paths:
            print("rm: отсутствует операнд"); return
        for p in paths:
            self.vfs.remove(p, recursive, force)

    # ---------- VFS-специфичные ----------
    def cmd_vfs_save(self, args):
        if not args:
            print("vfs-save: укажите путь для сохранения"); return
        if not self.vfs_loaded:
            print("vfs-save: VFS не загружена"); return
        self.vfs.save_to_zip(args[0])

    def cmd_vfs_info(self, args):
        if not self.vfs_loaded:
            print("VFS не загружена"); return
        st = self.vfs.get_stats()
        print("Информация о VFS:")
        print(f"  Источник: {self.vfs.loaded_from}")
        print(f"  Файлов: {st['files']}")
        print(f"  Директорий: {st['directories']}")
        print(f"  Общий размер: {st['total_size']} байт")
        print(f"  Текущая директория: {self.vfs.get_current_path()}")

    def cmd_exit(self, args):
        print("Выход...")
        self.running = False

    # ---------- скрипты (Этап 2) ----------
    def run_script(self, script_path):
        print(f"\n--- Выполнение скрипта: {script_path} ---")
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                for line_no, line in enumerate(f, 1):
                    line = line.rstrip('\n\r')
                    if not line.strip() or line.strip().startswith('#'):
                        continue
                    print(f"{self.get_prompt()}{line}")
                    cmd, args = self.parse_command(line)
                    if cmd:
                        self.execute(cmd, args)
        except FileNotFoundError:
            print(f"Ошибка: скрипт не найден: {script_path}")
        except Exception as e:
            print(f"Ошибка при выполнении скрипта: {e}")

    # ---------- главный цикл (Этап 1) ----------
    def run(self):
        if self.cfg.debug:
            print("=" * 60)
            print("ОТЛАДКА: параметры запуска")
            print(f"  VFS: {self.cfg.vfs_path}")
            print(f"  Стартовый скрипт: {self.cfg.startup_script}")
            print(f"  Загружено VFS: {self.vfs_loaded}")
            print("=" * 60)

        if self.cfg.startup_script:
            self.run_script(self.cfg.startup_script)

        print("Эмулятор shell (этапы 1–5). Введите 'exit' для выхода.")
        while self.running:
            try:
                user_in = input(self.get_prompt()).strip()
                if not user_in:
                    continue
                cmd, args = self.parse_command(user_in)
                if cmd:
                    self.execute(cmd, args)
            except KeyboardInterrupt:
                print("\nИспользуйте 'exit'")
            except EOFError:
                print("\nВыход...")
                break

def main():
    cfg = parse_arguments()
    if not validate_config(cfg):
        sys.exit(1)
    ShellEmulator(cfg).run()

if __name__ == '__main__':
    main()