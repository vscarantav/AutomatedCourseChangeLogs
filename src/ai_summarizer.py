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
        model = genai.GenerativeModel('gemini-3.8-flash')
        
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

def summarize_course_changes(file_summaries: list) -> dict:
    """
    Uses Gemini API to generate a high-level course summary and impact ranking from a list of file changes.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"summary": "AI Summarization disabled: GEMINI_API_KEY not found in environment.", "impact": "N/A"}
        
    if not file_summaries:
        return {"summary": "No AI summaries available to aggregate.", "impact": "N/A"}
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-3.8-flash')
        
        summaries_text = "\n".join([f"- {s}" for s in file_summaries if s and not s.startswith("AI Summarization disabled") and not s.startswith("AI Summarization failed")])
        if not summaries_text.strip():
            return {"summary": "No substantive changes were able to be summarized by the AI.", "impact": "Low"}
            
        prompt = f"""
You are an expert instructional designer and Canvas LMS administrator. 
Analyze the following list of individual file changes that occurred in a single Canvas course this week.

Individual Changes:
{summaries_text}

Provide two things:
1. A concise, holistic 2-4 sentence summary of the overarching changes made to the course this week. Focus on the impact to the student experience and the significance of the changes to the instructional designer.
2. An 'Impact Ranking' which must be EXACTLY one of the following words: Low, Medium, High. Determine this by evaluating how significant the changes are for course maintenance and the student's daily life.

Format your response exactly like this:
Impact: [Low/Medium/High]
Summary: [Your 2-4 sentence summary]
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        impact = "Medium"
        summary = text
        
        import re
        impact_match = re.search(r'Impact:\s*(Low|Medium|High)', text, re.IGNORECASE)
        if impact_match:
            impact = impact_match.group(1).capitalize()
            
        summary_match = re.search(r'Summary:\s*(.*)', text, re.IGNORECASE | re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()
            
        return {"summary": summary, "impact": impact}
    except Exception as e:
        return {"summary": f"Course AI Summarization failed: {e}", "impact": "N/A"}
