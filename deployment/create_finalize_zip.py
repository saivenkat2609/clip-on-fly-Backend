"""
Create opus-finalize.zip with firebase-admin
Handles SSL certificate issues better than pip CLI
"""
import subprocess
import sys
import os
import shutil
import zipfile
from pathlib import Path

def main():
    print("=" * 50)
    print("Creating opus-finalize.zip")
    print("=" * 50)
    print()

    # Directories
    script_dir = Path(__file__).parent
    build_dir = script_dir / "build-finalize"
    src_dir = script_dir.parent / "src"

    # Clean build directory
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()

    print("[1/5] Copying lambda_function.py...")
    shutil.copy(src_dir / "finalize" / "lambda_function.py", build_dir)

    print("[2/5] Copying shared modules...")
    shared_dir = build_dir / "shared"
    shared_dir.mkdir()
    for py_file in (src_dir / "shared").glob("*.py"):
        shutil.copy(py_file, shared_dir)

    print("[3/5] Installing firebase-admin...")
    print("This may take a few minutes...")

    try:
        # Try with SSL verification disabled
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "firebase-admin==6.5.0",
            "-t", str(build_dir),
            "--trusted-host", "pypi.org",
            "--trusted-host", "files.pythonhosted.org",
            "--upgrade",
            "--no-cache-dir"
        ])
        print("✓ firebase-admin installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install firebase-admin: {e}")
        print("\nTrying alternative method...")

        # Alternative: use system Python's certifi
        try:
            import ssl
            import certifi
            ssl._create_default_https_context = ssl._create_unverified_context

            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "firebase-admin==6.5.0",
                "-t", str(build_dir),
                "--upgrade",
                "--no-cache-dir"
            ])
            print("✓ firebase-admin installed successfully (alternative method)")
        except Exception as e2:
            print(f"ERROR: Both methods failed: {e2}")
            print("\nPlease try:")
            print("1. pip install --upgrade certifi")
            print("2. Run this script again")
            sys.exit(1)

    print("\n[4/5] Creating zip file...")
    zip_path = script_dir / "opus-finalize.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(build_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(build_dir)
                zipf.write(file_path, arcname)

    print(f"✓ Created: {zip_path}")

    print("\n[5/5] Cleaning up...")
    shutil.rmtree(build_dir)

    # Get zip size
    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 50)
    print("SUCCESS!")
    print("=" * 50)
    print(f"\nZip file: {zip_path}")
    print(f"Size: {zip_size_mb:.2f} MB")
    print("\nNext steps:")
    print("1. Go to AWS Lambda Console")
    print("2. Open function: opus-finalize")
    print("3. Click 'Upload from' → '.zip file'")
    print("4. Select: opus-finalize.zip")
    print("5. Click 'Save'")
    print()

if __name__ == "__main__":
    main()
