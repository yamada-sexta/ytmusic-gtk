def mac_brew_fix():
    try:
        import subprocess
        import os
        import sys
        brew_prefix = subprocess.check_output(["brew", "--prefix"], text=True).strip()
        brew_lib_path = f"{brew_prefix}/lib"

        os.environ["GI_TYPELIB_PATH"] = f"{brew_lib_path}/girepository-1.0"
        current_dyld = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")

        if brew_lib_path not in current_dyld:
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{brew_lib_path}:{current_dyld}"
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"Warning: Could not configure Homebrew paths automatically: {e}")

