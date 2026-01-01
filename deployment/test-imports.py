"""
Test Lambda function to check what packages are available
Replace your lambda_function.py temporarily with this to debug
"""
import sys
import os

def lambda_handler(event, context):
    print("=" * 50)
    print("DEBUGGING IMPORTS")
    print("=" * 50)

    # Print Python path
    print("\nPython sys.path:")
    for path in sys.path:
        print(f"  - {path}")

    # Check /opt directory (where layers are mounted)
    print("\n/opt directory contents:")
    if os.path.exists('/opt'):
        for item in os.listdir('/opt'):
            print(f"  - {item}")
            if item == 'python':
                print("    /opt/python contents:")
                python_path = '/opt/python'
                if os.path.exists(python_path):
                    for sub_item in os.listdir(python_path)[:20]:  # First 20 items
                        print(f"      - {sub_item}")
    else:
        print("  /opt does not exist!")

    # Try importing firebase_admin
    print("\nTrying to import firebase_admin:")
    try:
        import firebase_admin
        print(f"  ✓ SUCCESS! firebase_admin version: {firebase_admin.__version__}")
        print(f"  Location: {firebase_admin.__file__}")
    except ImportError as e:
        print(f"  ✗ FAILED: {str(e)}")

    # Try importing google.cloud.firestore
    print("\nTrying to import google.cloud.firestore:")
    try:
        from google.cloud import firestore
        print(f"  ✓ SUCCESS! firestore imported")
    except ImportError as e:
        print(f"  ✗ FAILED: {str(e)}")

    # List all installed packages
    print("\nInstalled packages (from site-packages):")
    try:
        import pkg_resources
        for pkg in sorted(pkg_resources.working_set, key=lambda x: str(x)):
            print(f"  - {pkg}")
    except:
        print("  Could not list packages")

    print("=" * 50)

    return {
        'statusCode': 200,
        'body': 'Check CloudWatch logs for debug output'
    }
