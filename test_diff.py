import os
import sys
import shutil

# Add src to python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from imscc_handler import extract_imscc
from differ import generate_diff_data
from html_reporter import generate_html_report

def run_test():
    course_folder = sys.argv[1] if len(sys.argv) > 1 else "GS170"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    course_dir = os.path.join(base_dir, 'all_courses_history', course_folder)
    
    if not os.path.exists(course_dir):
        print(f"Error: Directory {course_dir} does not exist.")
        return

    # Load environment variables for the Gemini API key
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(base_dir, '.env'))
    except ImportError:
        pass

    old_dir = os.path.join(course_dir, 'old')
    new_dir = os.path.join(course_dir, 'new')
    
    # Automatically organize files if they are loose in the folder
    files = os.listdir(course_dir)
    for f in files:
        path = os.path.join(course_dir, f)
        if os.path.isdir(path): continue
        
        lower = f.lower()
        if 'old' in lower:
            os.makedirs(old_dir, exist_ok=True)
            shutil.move(path, os.path.join(old_dir, 'old.imscc'))
        elif 'new' in lower:
            os.makedirs(new_dir, exist_ok=True)
            shutil.move(path, os.path.join(new_dir, 'new.imscc'))

    old_imscc = os.path.join(old_dir, 'old.imscc')
    new_imscc = os.path.join(new_dir, 'new.imscc')
    
    print("Extracting old IMSCC...")
    try:
        old_extract_dir = extract_imscc(old_imscc)
    except Exception as e:
        print(f"Failed to extract old IMSCC: {e}")
        return
        
    print("Extracting new IMSCC...")
    try:
        new_extract_dir = extract_imscc(new_imscc)
    except Exception as e:
        print(f"Failed to extract new IMSCC: {e}")
        return
    
    print(f"\nGenerating Diff Data for {course_folder}...")
    course_data = generate_diff_data(old_extract_dir, new_extract_dir, f"Course Changes for {course_folder}")
    
    print("Generating HTML Report...")
    report_html = generate_html_report(f"{course_folder}_Analysis", [course_data])
    
    report_path = os.path.join(course_dir, f'report_{course_folder}.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_html)
        
    print(f"\nReport generated at: {report_path}")

if __name__ == "__main__":
    run_test()
