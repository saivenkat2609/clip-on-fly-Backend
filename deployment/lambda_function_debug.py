"""
DEBUG VERSION - Shows what packages Lambda can import
"""
import sys
import os
import json

def lambda_handler(event, context):
    debug_info = {
        "python_version": sys.version,
        "python_path": sys.path,
        "opt_exists": os.path.exists('/opt'),
        "opt_contents": [],
        "firebase_admin_status": "NOT CHECKED"
    }

    print("=" * 60)
    print("LAMBDA DEBUGGING INFO")
    print("=" * 60)

    print(f"\nPython Version: {sys.version}")

    print("\nPython sys.path:")
    for path in sys.path:
        print(f"  {path}")

    # Check /opt directory
    print("\n/opt directory:")
    if os.path.exists('/opt'):
        print("  EXISTS!")
        try:
            opt_contents = os.listdir('/opt')
            debug_info["opt_contents"] = opt_contents
            print(f"  Contents: {opt_contents}")

            # Check /opt/python
            if 'python' in opt_contents:
                print("\n  /opt/python directory:")
                python_dir = '/opt/python'
                python_contents = os.listdir(python_dir)
                print(f"    Count: {len(python_contents)} items")
                print(f"    First 30 items: {python_contents[:30]}")

                # Look for firebase_admin
                if 'firebase_admin' in python_contents:
                    print("\n    ✓ firebase_admin folder FOUND in /opt/python!")
                else:
                    print("\n    ✗ firebase_admin folder NOT FOUND in /opt/python")
                    print(f"    Available packages: {[p for p in python_contents if not p.startswith('_')][:20]}")
        except Exception as e:
            print(f"  Error reading /opt: {e}")
    else:
        print("  DOES NOT EXIST!")

    # Try importing firebase_admin
    print("\n" + "-" * 60)
    print("ATTEMPTING TO IMPORT firebase_admin:")
    print("-" * 60)

    try:
        import firebase_admin
        debug_info["firebase_admin_status"] = "SUCCESS"
        print(f"✓ SUCCESS! Version: {firebase_admin.__version__}")
        print(f"  Location: {firebase_admin.__file__}")
    except ImportError as e:
        debug_info["firebase_admin_status"] = f"FAILED: {str(e)}"
        print(f"✗ IMPORT FAILED: {e}")
        print("\nChecking sys.modules for firebase:")
        firebase_modules = [m for m in sys.modules.keys() if 'firebase' in m.lower()]
        print(f"  Firebase modules loaded: {firebase_modules}")
    except Exception as e:
        debug_info["firebase_admin_status"] = f"ERROR: {str(e)}"
        print(f"✗ UNEXPECTED ERROR: {e}")

    # Check environment variables
    print("\n" + "-" * 60)
    print("ENVIRONMENT VARIABLES:")
    print("-" * 60)
    firebase_vars = {k: v for k, v in os.environ.items() if 'FIREBASE' in k}
    print(f"Firebase-related vars: {list(firebase_vars.keys())}")

    # Check function configuration
    print("\n" + "-" * 60)
    print("LAMBDA CONTEXT:")
    print("-" * 60)
    print(f"Function name: {context.function_name}")
    print(f"Memory limit: {context.memory_limit_in_mb} MB")
    print(f"Remaining time: {context.get_remaining_time_in_millis()} ms")

    print("\n" + "=" * 60)
    print("END DEBUG INFO")
    print("=" * 60)

    return {
        'statusCode': 200,
        'body': json.dumps(debug_info, indent=2)
    }
