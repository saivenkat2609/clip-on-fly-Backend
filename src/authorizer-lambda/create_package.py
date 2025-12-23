import zipfile
import os
from pathlib import Path

def create_lambda_package():
    """Create Lambda deployment package"""
    source_dir = Path('.')
    output_file = 'authorizer-lambda.zip'

    if os.path.exists(output_file):
        os.remove(output_file)

    print(f'Creating {output_file}...')

    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv']]

            for file in files:
                if file.endswith(('.pyc', '.pyo')) or file in ['create_package.py', 'authorizer-lambda.zip']:
                    continue

                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)

    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f'Created: {output_file} ({size_mb:.2f} MB)')

    # Verify key files
    with zipfile.ZipFile(output_file, 'r') as zipf:
        files_in_zip = zipf.namelist()
        has_lambda = 'lambda_function.py' in files_in_zip
        has_jwt = any('jwt/' in f for f in files_in_zip)
        print(f'lambda_function.py: {"YES" if has_lambda else "NO"}')
        print(f'jwt package: {"YES" if has_jwt else "NO"}')

if __name__ == '__main__':
    create_lambda_package()
