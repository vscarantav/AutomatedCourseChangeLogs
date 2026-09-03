import os
import google.generativeai as genai

def summarize_change(page_content: str, diff_lines: list, filename: str) -> str:
    """
    Uses Gemini API to summarize the change given the page context and the diff.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "AI Summarization disabled: GEMINI_API_KEY not found in environment."
        
    try:
        genai.configure(api_key=api_key)
        # Using flash for fast, cheap inference
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # We limit page content to avoid massive token usage for huge files
        content_snippet = page_content[:15000] if page_content else "No content available."
        diff_text = "\n".join(diff_lines)
        
        prompt = f"""
You are an expert instructional designer and Canvas LMS administrator. 
Analyze the following file change in a Canvas course.

File: {filename}

Context (Full Page Text Snippet):
{content_snippet}

Diff (Changes):
{diff_text}

Provide a very short, direct, and explanatory 1-2 sentence human-readable summary of what changed from the perspective of a teacher or student. Focus only on the substantive change (e.g., "The due date was extended by two days" or "A new paragraph about grading policies was added"). Do not mention UUIDs, HTML tags, or system metadata. Be extremely direct and avoid all conversational filler.
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI Summarization failed: {e}"
