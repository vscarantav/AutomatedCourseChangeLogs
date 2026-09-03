import os
import zipfile

def extract_imscc(imscc_path: str, delete_after: bool = True):
    """
    Extracts the IMSCC zip file into a subdirectory named after the zip file.
    Detects if the zip contains a nested folder and returns the true root containing imsmanifest.xml.
    """
    if not os.path.exists(imscc_path):
        raise FileNotFoundError(f"IMSCC file not found: {imscc_path}")
        
    export_dir = os.path.dirname(imscc_path)
    base_name = os.path.splitext(os.path.basename(imscc_path))[0]
    extract_dir = os.path.join(export_dir, f"{base_name}_extracted")
    
    os.makedirs(extract_dir, exist_ok=True)
    
    print(f"Extracting {imscc_path} to {extract_dir}...")
    with zipfile.ZipFile(imscc_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    # Delete original zip to save space if requested
    if delete_after:
        try:
            os.remove(imscc_path)
            print(f"Deleted original IMSCC file to optimize storage: {imscc_path}")
        except Exception as e:
            print(f"Failed to delete {imscc_path}: {e}")
            
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
