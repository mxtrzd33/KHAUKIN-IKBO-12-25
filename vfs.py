# vfs.py
import zipfile
import base64
import io
import time
from typing import Dict, List, Optional
from pathlib import PurePosixPath

class VFSNode:
    def __init__(self, name: str, is_dir: bool = False, content: bytes = b"", parent=None):
        self.name = name
        self.is_dir = is_dir
        self.content = content
        self.parent = parent
        self.children: Dict[str, VFSNode] = {}
        self.owner = "user"
        self.group = "user"
        self.mtime = time.time()

class VirtualFileSystem:
    def __init__(self):
        self.root = VFSNode("/", is_dir=True)
        self.cwd = self.root
        self.loaded_from = None
        self._file_count = 0
        self._dir_count = 1   # root

    # ---------- загрузка ----------
    def load_from_zip(self, path) -> bool:
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                self._build_from_zip(zf)
            self.loaded_from = str(path)
            return True
        except FileNotFoundError:
            print(f"VFS: файл не найден: {path}")
            return False
        except zipfile.BadZipFile:
            print(f"VFS: неверный формат ZIP: {path}")
            return False

    def _build_from_zip(self, zf: zipfile.ZipFile):
        for info in zf.infolist():
            parts = PurePosixPath(info.filename).parts
            node = self.root
            for part in parts[:-1]:
                if part not in node.children:
                    new_dir = VFSNode(part, is_dir=True, parent=node)
                    node.children[part] = new_dir
                    self._dir_count += 1
                node = node.children[part]
            last = parts[-1]
            if info.is_dir():
                if last not in node.children:
                    node.children[last] = VFSNode(last, is_dir=True, parent=node)
                    self._dir_count += 1
            else:
                data = zf.read(info.filename)
                node.children[last] = VFSNode(last, is_dir=False, content=data, parent=node)
                self._file_count += 1

    def load_from_base64(self, b64_str: str) -> bool:
        try:
            raw = base64.b64decode(b64_str)
            with zipfile.ZipFile(io.BytesIO(raw), 'r') as zf:
                self._build_from_zip(zf)
            self.loaded_from = "base64"
            return True
        except Exception as e:
            print(f"VFS: ошибка base64: {e}")
            return False

    # ---------- навигация ----------
    def _resolve(self, path: str) -> Optional[VFSNode]:
        if not path or path == ".":
            return self.cwd
        if path.startswith("/"):
            node = self.root
            components = PurePosixPath(path).parts[1:]
        else:
            node = self.cwd
            components = PurePosixPath(path).parts
        for comp in components:
            if comp == ".":
                continue
            if comp == "..":
                if node.parent:
                    node = node.parent
                continue
            if not node.is_dir or comp not in node.children:
                return None
            node = node.children[comp]
        return node

    def change_directory(self, path: str):
        node = self._resolve(path)
        if node is None:
            print(f"cd: {path}: Нет такого файла или каталога")
        elif not node.is_dir:
            print(f"cd: {path}: Не является каталогом")
        else:
            self.cwd = node

    def get_current_path(self) -> str:
        if self.cwd is self.root:
            return "/"
        parts = []
        n = self.cwd
        while n is not self.root:
            parts.append(n.name)
            n = n.parent
        return "/" + "/".join(reversed(parts))

    # ---------- чтение ----------
    def list_directory(self, path: str, show_all: bool, long_format: bool) -> List[str]:
        node = self._resolve(path) if path else self.cwd
        if node is None:
            return [f"ls: {path}: Нет такого файла или каталога"]
        if not node.is_dir:
            return [node.name] if not long_format else [self._format_long(node)]
        items = sorted(node.children.values(), key=lambda n: n.name)
        if not show_all:
            items = [n for n in items if not n.name.startswith('.')]
        if long_format:
            return [self._format_long(n) for n in items]
        return [n.name for n in items]

    def _format_long(self, node: VFSNode) -> str:
        typ = 'd' if node.is_dir else '-'
        size = len(node.content) if not node.is_dir else 0
        return f"{typ}rw-r--r-- 1 {node.owner} {node.group} {size:>6} {node.name}"

    def cat(self, path: str):
        node = self._resolve(path)
        if node is None:
            print(f"cat: {path}: Нет такого файла или каталога")
            return
        if node.is_dir:
            print(f"cat: {path}: Это каталог")
            return
        try:
            print(node.content.decode('utf-8'))
        except UnicodeDecodeError:
            b64 = base64.b64encode(node.content).decode('ascii')
            print(f"[Бинарный файл, base64]:\n{b64}")

    def find(self, pattern: str) -> List[str]:
        results = []
        def walk(node: VFSNode, prefix: str):
            for name, child in node.children.items():
                full = f"{prefix}/{name}" if prefix != "/" else f"/{name}"
                if self._match(name, pattern):
                    results.append(full)
                if child.is_dir:
                    walk(child, full)
        walk(self.root, "/")
        return results

    @staticmethod
    def _match(name: str, pattern: str) -> bool:
        import fnmatch
        return fnmatch.fnmatch(name, pattern)

    # ---------- изменение (Этап 5) ----------
    def touch(self, path: str):
        parent_path = str(PurePosixPath(path).parent)
        name = PurePosixPath(path).name
        parent = self._resolve(parent_path) if parent_path not in ('.', '') else self.cwd
        if parent is None or not parent.is_dir:
            print(f"touch: не удалось создать '{path}': нет такого каталога")
            return
        if name in parent.children:
            parent.children[name].mtime = time.time()
        else:
            parent.children[name] = VFSNode(name, is_dir=False, content=b"", parent=parent)
            self._file_count += 1
            parent.children[name].mtime = time.time()

    def move(self, src: str, dst: str):
        src_node = self._resolve(src)
        if src_node is None:
            print(f"mv: '{src}': Нет такого файла или каталога")
            return
        dst_path = PurePosixPath(dst)
        if dst_path.name == '':
            # перемещение в существующую директорию
            dst_dir = self._resolve(dst)
            if dst_dir is None or not dst_dir.is_dir:
                print(f"mv: '{dst}': Не является каталогом")
                return
            new_name = src_node.name
        else:
            dst_dir = self._resolve(str(dst_path.parent)) if str(dst_path.parent) not in ('.', '') else self.cwd
            new_name = dst_path.name
            if dst_dir is None or not dst_dir.is_dir:
                print(f"mv: '{dst}': Не является каталогом")
                return
        # проверка на конфликт
        if new_name in dst_dir.children and dst_dir.children[new_name] is not src_node:
            print(f"mv: '{dst}': уже существует")
            return
        # удаление из старого места
        if src_node.parent:
            del src_node.parent.children[src_node.name]
        src_node.parent = dst_dir
        src_node.name = new_name
        dst_dir.children[new_name] = src_node

    def remove(self, path: str, recursive: bool = False, force: bool = False):
        node = self._resolve(path)
        if node is None:
            if not force:
                print(f"rm: '{path}': Нет такого файла или каталога")
            return
        if node is self.root:
            print("rm: невозможно удалить корневую директорию")
            return
        if node.is_dir and not recursive:
            print(f"rm: '{path}': это каталог (используйте -r)")
            return
        if node.parent:
            del node.parent.children[node.name]
            if node.is_dir:
                self._dir_count -= 1
            else:
                self._file_count -= 1

    # ---------- сохранение (Этап 3) ----------
    def save_to_zip(self, dest_path: str):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            def add_node(node: VFSNode, prefix: str = ""):
                for name, child in node.children.items():
                    full = f"{prefix}{name}"
                    if child.is_dir:
                        zf.writestr(full + "/", b"")
                        add_node(child, full + "/")
                    else:
                        zf.writestr(full, child.content)
            add_node(self.root)
        with open(dest_path, 'wb') as f:
            f.write(buf.getvalue())
        print(f"VFS сохранена в {dest_path}")

    # ---------- статистика ----------
    def get_stats(self) -> dict:
        total = 0
        def calc(node: VFSNode):
            nonlocal total
            for child in node.children.values():
                if child.is_dir:
                    calc(child)
                else:
                    total += len(child.content)
        calc(self.root)
        return {'files': self._file_count, 'directories': self._dir_count, 'total_size': total}