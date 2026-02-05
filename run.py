#!/usr/bin/env python3
import sys
import subprocess
import os
import shutil
from pathlib import Path

def is_venv():
    """Check if running inside a virtual environment."""
    return (hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

def get_venv_python():
    """Get path to venv python executable."""
    if sys.platform == "win32":
        return os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")
    return os.path.join(os.getcwd(), "venv", "bin", "python")

def bootstrap():
    """Ensure venv exists and deps are installed, then re-exec."""
    print(">> Ortam kontrolu yapiliyor...")
    
    venv_dir = Path("venv")
    venv_python = get_venv_python()
    
    # 1. Create Venv if missing
    if not venv_dir.exists():
        print(f"[!] Sanal ortam (venv) bulunamadi. Olusturuluyor...")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", "venv"])
            print("[+] Venv olusturuldu.")
        except Exception as e:
            print(f"[ERROR] Venv olusturulamadi: {e}")
            sys.exit(1)

    # 2. Check Dependencies (Simple check)
    # We try to run a pip check or just always install if not sure?
    # Better: check if we can import key modules using the VENV python
    # But checking from OUTSIDE is hard. 
    # Let's just rely on the fact that if we are NOT in venv, we restart IN venv.
    # The Code inside venv will check imports.
    
    if not is_venv():
        print(f">> Sanal ortam baslatiliyor: {venv_python}")
        
        # Check permissions on linux
        if sys.platform != "win32":
            if os.path.exists(venv_python):
                os.chmod(venv_python, 0o755)
        
        if not os.path.exists(venv_python):
             print(f"[ERROR] Python venv binary bulunamadi: {venv_python}")
             print("Lutfen 'venv' klasorunu silip tekrar deneyin.")
             sys.exit(1)

        # Re-execute explicitly with venv python
        # We assume requirements are needed if we just created it, 
        # OR let the inner process check imports.
        # Let's force install/upgrade requirements from the wrapper to be safe 
        # BEFORE switching, using the venv pip.
        
        print(">> Paket kontrolu...")
        pip_cmd = [venv_python, "-m", "pip", "install", "-r", "requirements.txt", "--quiet", "--disable-pip-version-check"]
        try:
            subprocess.check_call(pip_cmd)
        except subprocess.CalledProcessError:
             print("[!] Gereksinimler yuklenemedi. 'requirements.txt' dosyasini kontrol edin.")
             # We continue anyway, maybe it works
        
        # Re-exec
        os.execv(venv_python, [venv_python] + sys.argv)

def check_dependencies():
    """Check imports inside the venv."""
    try:
        import textual
        import rich
        from googleapiclient.discovery import build
        import google_auth_oauthlib
        import google.auth.transport.requests
        return True
    except ImportError as e:
        return e.name

def main():
    # Only bootstrap if not already in venv
    if not is_venv():
        bootstrap()
        # bootstrap calls execv, so we never reach here except error
        return

    # If we are here, we are IN venv (or failed detection)
    
    missing = check_dependencies()
    if missing is not True:
        print(f"\n[!] Venv icinde eksik kutuphane: {missing}")
        print("Otomatik yukleniyor...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
    print("========================================")
    print("   AutoVideo Baslatici (Launcher)      ")
    print("========================================")
    print(f"Mod: {'VENV' if is_venv() else 'SYSTEM'}")
    print("1. Normal Mod (Uretim, Video Render)")
    print("2. Ramtest Modu (Gelistirici/Test)")
    print("q. Cikis")
    print("========================================")
    
    choice = input("Seciminiz (1/2/q) [1]: ").strip().lower()
    
    if choice == 'q':
        sys.exit(0)
        
    if not choice:
        choice = '1'
        
    cmd = []
    
    if choice == '1':
        print("\n>> Normal Mod baslatiliyor...")
        cmd = [sys.executable, "-m", "video_renderer", "--tui"]
        
    elif choice == '2':
        print("\n>> Ramtest Modu baslatiliyor...")
        cmd = [sys.executable, "-m", "video_renderer_ramtest", "--tui"]
        
    else:
        print("Gecersiz secim!")
        sys.exit(1)
        
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nIptal edildi.")
    except Exception as e:
        print(f"\nHata olustu: {e}")
        input("Cikmak icin Enter'a basin...")

if __name__ == "__main__":
    main()
