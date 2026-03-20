#!/usr/bin/env python3
"""
AutoVideo Bootstrap and Launcher

Ensures virtual environment exists, dependencies are installed,
and properly launches the application with clean terminal handling.
"""

import atexit
import os
import subprocess
import sys
from pathlib import Path


def is_venv():
    """Check if running inside a virtual environment."""
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def get_venv_python():
    """Get path to venv python executable."""
    if sys.platform == "win32":
        return os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")
    return os.path.join(os.getcwd(), "venv", "bin", "python")


def _cleanup_on_exit():
    """Cleanup terminal settings on exit."""
    try:
        sys.stdout.flush()
        sys.stderr.flush()

        # Linux: Restore terminal settings
        if sys.platform != "win32":
            try:
                os.system("stty sane 2>/dev/null")
            except Exception:
                pass
    except Exception:
        pass


def bootstrap():
    """Ensure venv exists and deps are installed, then re-exec."""
    # Register cleanup handler
    atexit.register(_cleanup_on_exit)

    print(">> Ortam kontrolu yapiliyor...")

    venv_dir = Path("venv")
    venv_python = get_venv_python()

    # 1. Create Venv if missing
    if not venv_dir.exists():
        print("[!] Sanal ortam (venv) bulunamadi. Olusturuluyor...")
        try:
            subprocess.check_call([sys.executable, "-m", "venv", "venv"])
            print("[+] Venv olusturuldu.")
        except Exception as e:
            print(f"[ERROR] Venv olusturulamadi: {e}")
            sys.exit(1)

    if not is_venv():
        print(">> Sanal ortam baslatiliyor...")

        # Check permissions on linux
        if sys.platform != "win32":
            if os.path.exists(venv_python):
                os.chmod(venv_python, 0o755)

        if not os.path.exists(venv_python):
            print(f"[ERROR] Python venv binary bulunamadi: {venv_python}")
            print("Lutfen 'venv' klasorunu silip tekrar deneyin.")
            sys.exit(1)

        print(">> Paket kontrolu...")
        pip_cmd = [
            venv_python,
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
            "--quiet",
            "--disable-pip-version-check",
        ]
        try:
            subprocess.check_call(pip_cmd)
        except subprocess.CalledProcessError:
            print("[!] Gereksinimler yuklenemedi. 'requirements.txt' dosyasini kontrol edin.")

        # Re-exec in venv
        os.execv(venv_python, [venv_python] + sys.argv)


def check_dependencies():
    """Check imports inside the venv."""
    try:
        import google.auth.transport.requests
        import google_auth_oauthlib
        import rich
        import textual
        from googleapiclient.discovery import build

        return True
    except ImportError as e:
        return e.name


def main():
    # Register cleanup handler
    atexit.register(_cleanup_on_exit)

    # Only bootstrap if not already in venv
    if not is_venv():
        bootstrap()
        # bootstrap calls execv, so we never reach here except error
        return

    # If we are here, we are IN venv

    missing = check_dependencies()
    if missing is not True:
        print(f"\n[!] Venv icinde eksik kutuphane: {missing}")
        print("Otomatik yukleniyor...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
            )
        except subprocess.CalledProcessError:
            print("[!] Paket yüklemesi başarısız oldu, devam ediliyor...")

    # Direct passthrough mode (e.g. `python run.py --tui`)
    if len(sys.argv) > 1:
        cmd = [sys.executable, "-m", "video_renderer", *sys.argv[1:]]
        try:
            result = subprocess.run(
                cmd,
                stdin=None,
                stdout=None,
                stderr=None,
            )
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            print("\nİptal edildi.")
            sys.exit(130)
        except Exception as e:
            print(f"\nHata oluştu: {e}")
            sys.exit(1)
        return

    # Interactive menu mode
    print("\n" + "=" * 70)
    print("  AutoVideo Baslatici (Launcher)")
    print("=" * 70)
    print(f"  Mod: {'VENV' if is_venv() else 'SYSTEM'}")
    print()
    print("  1. CLI Mod (Interaktif Render Wizard)")
    print("  2. TUI Mod (Textual Arayuz)")
    print("  3. Smart Batch (Otomatik Intro/Loop Tespiti)")
    print("  q. Cikis")
    print("=" * 70)

    choice = input("\nSeciminiz (1/2/3/q) [1]: ").strip().lower()

    if choice == "q":
        sys.exit(0)

    if not choice:
        choice = "1"

    cmd = []

    if choice == "1":
        # CLI Interactive Mode (DEFAULT)
        print("\n>> CLI Interaktif Mod baslatiliyor...\n")
        cmd = [sys.executable, "-m", "video_renderer"]

    elif choice == "2":
        # TUI Mode (Textual)
        print("\n>> TUI Mod baslatiliyor...\n")
        cmd = [sys.executable, "-m", "video_renderer", "--tui"]

    elif choice == "3":
        # Smart Batch Mode
        print("\n>> Smart Batch Mod baslatiliyor...\n")
        cmd = [sys.executable, "-m", "video_renderer", "--batch"]

    else:
        print("Gecersiz secim!")
        sys.exit(1)

    try:
        result = subprocess.run(
            cmd,
            stdin=None,
            stdout=None,
            stderr=None,
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nİptal edildi.")
        sys.exit(130)
    except Exception as e:
        print(f"\nHata oluştu: {e}")
        try:
            input("Çıkmak için Enter'a basın...")
        except (KeyboardInterrupt, EOFError):
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
