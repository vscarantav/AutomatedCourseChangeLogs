import os
import zipfile

def extract_imscc(imscc_path: str):
    """
    Extracts the IMSCC zip file into an 'extracted' subdirectory alongside the zip.
    Detects if the zip contains a nested folder and returns the true root containing imsmanifest.xml.
    """
    if not os.path.exists(imscc_path):
        raise FileNotFoundError(f"IMSCC file not found: {imscc_path}")
        
    export_dir = os.path.dirname(imscc_path)
    extract_dir = os.path.join(export_dir, 'extracted')
    
    os.makedirs(extract_dir, exist_ok=True)
    
    print(f"Extracting {imscc_path} to {extract_dir}...")
    with zipfile.ZipFile(imscc_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    # Check for nested root (common in some Canvas exports where a single top-level folder exists)
    manifest_path = os.path.join(extract_dir, 'imsmanifest.xml')
    if not os.path.exists(manifest_path):
        # Look one level deep
        subdirs = [os.path.join(extract_dir, d) for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
        if len(subdirs) == 1:
            nested_manifest = os.path.join(subdirs[0], 'imsmanifest.xml')
            if os.path.exists(nested_manifest):
                print(f"Found nested directory structure. True root is {subdirs[0]}")
                return subdirs[0]
                
    print("Extraction complete.")
    return extract_dir
