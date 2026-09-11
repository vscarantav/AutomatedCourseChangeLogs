import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))

# Add the 'src' and 'scripts' directories to the Python path
src_path = os.path.join(root_dir, 'src')
scripts_path = os.path.join(root_dir, 'scripts')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

# pyrefly: ignore [missing-import]
import fetch_exports
# pyrefly: ignore [missing-import]
import main

if __name__ == '__main__':
    print("Fetching today's Canvas exports...")
    fetch_exports.main()
    print("\nGenerating course change reports...")
    main.main()
