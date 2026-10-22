# scripts/create_vfs_archives.py
import zipfile
from pathlib import Path

DEST = Path(__file__).parent.parent / "vfs_archives"
DEST.mkdir(exist_ok=True)

def create_zip(name, files):
    path = DEST / name
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files.items():
            if fname.endswith('/'):
                zf.writestr(fname, b'')
            else:
                zf.writestr(fname, content)
    print(f"Создан: {path}")

# 1. Минимальный VFS
create_zip('minimal_vfs.zip', {
    'readme.txt': b'Hello, VFS!\n',
})

# 2. Несколько файлов
create_zip('medium_vfs.zip', {
    'home/user/notes.txt': b'Some notes\n',
    'home/user/data.csv': b'a,b,c\n1,2,3\n',
    'etc/config.json': b'{"key":"value"}\n',
})

# 3. Глубина 3+ уровней
create_zip('complex_vfs.zip', {
    'home/user/documents/report.txt': b'Report content\n',
    'home/user/documents/archive/old.txt': b'old data\n',
    'home/user/downloads/file.bin': b'\x00\x01\x02',
    'etc/nginx/nginx.conf': b'server { listen 80; }\n',
    'var/log/syslog.log': b'log entry\n',
    'tmp/empty/': b'',
})