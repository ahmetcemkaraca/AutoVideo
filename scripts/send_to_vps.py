#!/usr/bin/env python3
"""
Script to zip and send the project to a VPS via TCP.
Acts as a netcat client for file transfer.

Usage:
  1. On VPS:  nc -l -p 12345 > deploy.zip
  2. On PC:   python scripts/send_to_vps.py <VPS_IP> 12345
"""

import sys
import socket
import zipfile
import io
from pathlib import Path

# Configuration
EXCLUDE_EXTENSIONS = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.pyc', '.zip', '.w64'}
EXCLUDE_DIRS = {'tmp', '__pycache__', '.git', '.vscode', 'venv', 'env', 'archive', 'music'}
INCLUDE_DIRS = {'video_renderer', 'scripts'}
INCLUDE_FILES = {'requirements.txt', 'setup.py', 'README.md', 'run.py'}

def should_include(path: Path, root: Path) -> bool:
    # Check directory exclusions
    for part in path.relative_to(root).parts:
        if part in EXCLUDE_DIRS:
            return False
            
    # Check extension exclusions
    if path.suffix.lower() in EXCLUDE_EXTENSIONS:
        return False
        
    return True

def create_project_zip() -> bytes:
    """Create a zip file of the project in memory."""
    print("Paket hazirlaniyor...")
    buffer = io.BytesIO()
    root = Path.cwd()
    
    count = 0
    total_size = 0
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add specific root files
        for fname in INCLUDE_FILES:
            fpath = root / fname
            if fpath.exists():
                print(f"  + {fname}")
                zf.write(fpath, fname)
                count += 1
                total_size += fpath.stat().st_size
        
        # Add directories
        for dirname in INCLUDE_DIRS:
            dirpath = root / dirname
            if not dirpath.exists():
                continue
                
            for file in dirpath.rglob('*'):
                if file.is_file() and should_include(file, root):
                    arcname = file.relative_to(root)
                    # print(f"  + {arcname}")
                    zf.write(file, arcname)
                    count += 1
                    total_size += file.stat().st_size
    
    size_mb = buffer.tell() / (1024 * 1024)
    print(f"\nPaket hazir: {count} dosya, {size_mb:.2f} MB (sikiştırılmış)")
    return buffer.getvalue()

def send_data(ip: str, port: int, data: bytes):
    """Send data to server."""
    print(f"Baglaniyor: {ip}:{port}...")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10) # 10s connect timeout
            s.connect((ip, port))
            print("Baglanti saglandi! Veri gonderiliyor...")
            
            s.sendall(data)
            
            print("Gonderim tamamlandi! ✅")
            print("\nVPS uzerinde sunu calistirip zip'i acabilirsiniz:")
            print("  unzip deploy.zip -d video_renderer_deploy")
            
    except ConnectionRefusedError:
        print("HATA: Baglanti reddedildi. VPS'de 'nc -l -p <PORT>' komutunu calistirdiniz mi?")
    except Exception as e:
        print(f"HATA: {e}")

def main():
    if len(sys.argv) < 3:
        print("Kullanim: python scripts/send_to_vps.py <VPS_IP> <PORT>")
        print("\nOnce VPS'de su komutu calistirin:")
        print("  nc -l -p 12345 > deploy.zip")
        return
    
    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        print("Port numarasi hatali.")
        return
        
    zip_data = create_project_zip()
    send_data(host, port, zip_data)

if __name__ == "__main__":
    main()
