#!/usr/bin/env python3
import sys
import subprocess
import os

def main():
    print("========================================")
    print("   AutoVideo Baslatici (Launcher)      ")
    print("========================================")
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
        # Replace current process or run subprocess
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nIptal edildi.")
    except Exception as e:
        print(f"\nHata olustu: {e}")
        input("Cikmak icin Enter'a basin...")

if __name__ == "__main__":
    main()
