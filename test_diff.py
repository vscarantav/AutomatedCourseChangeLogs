import os
import sys

# Add src to python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from imscc_handler import extract_imscc
from differ import generate_diff_data
from html_reporter import generate_html_report

def run_test():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    old_imscc = os.path.join(base_dir, 'all_courses_history', 'old', 'old.imscc')
    new_imscc = os.path.join(base_dir, 'all_courses_history', 'new', 'New.imscc')
    
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
    
    print("\nGenerating Diff Data...")
    course_data = generate_diff_data(old_extract_dir, new_extract_dir, "Writing in Professional Contexts (English Master)")
    
    print("Generating HTML Report...")
    # Generate HTML report
    # We pass 'Test Week' and a list of course_data (since main script processes multiple courses)
    report_html = generate_html_report("2026_W34_Test", [course_data])
    
    report_path = os.path.join(base_dir, 'all_courses_history', 'test_report.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_html)
        
    print(f"\nReport generated at: {report_path}")

if __name__ == "__main__":
    run_test()
