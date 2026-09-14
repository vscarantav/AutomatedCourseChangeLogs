import os
from google import genai


MODEL_NAME = "gemini-3.8-flash"


def _generate_content(api_key: str, prompt: str) -> str:
    """Generate text with the supported Google Gen AI SDK."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    return (response.text or "").strip()

def summarize_change(page_content: str, diff_lines: list, filename: str) -> str:
    """
    Uses Gemini API to summarize the change given the page context and the diff.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "AI Summarization disabled: GEMINI_API_KEY not found in environment."
        
    try:
        # We limit page content to avoid massive token usage for huge files
        content_snippet = page_content[:15000] if page_content else "No content available."
        diff_text = "\n".join(diff_lines)
        
        prompt = f"""
You are an expert Course Designer and Canvas LMS administrator. 
Analyze the following file change in a Canvas course.

File: {filename}

Context (Full Page Text Snippet):
{content_snippet}

Diff (Changes):
{diff_text}

Provide a very short, direct, and explanatory 1-2 sentence human-readable summary of what changed from the perspective of a teacher or student. Focus only on the substantive change (e.g., "The due date was extended by two days" or "A new paragraph about grading policies was added"). Do not mention UUIDs, HTML tags, or system metadata. Be extremely direct and avoid all conversational filler.
"""
        return _generate_content(api_key, prompt)
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
        summaries_text = "\n".join([f"- {s}" for s in file_summaries if s and not s.startswith("AI Summarization disabled") and not s.startswith("AI Summarization failed")])
        if not summaries_text.strip():
            return {"summary": "No substantive changes were able to be summarized by the AI.", "impact": "Low"}
            
        prompt = f"""
You are an expert Course Designer and Canvas LMS administrator. 
Analyze the following list of individual file changes that occurred in a single Canvas course this week.

Individual Changes:
{summaries_text}

Provide two things:
1. A concise, holistic 2-4 sentence summary of the overarching changes made to the course this week. Focus on the impact to the student experience and the significance of the changes to the Course Designer.
2. An 'Impact Ranking' which must be EXACTLY one of the following words: Low, Medium, High. Determine this by evaluating how significant the changes are for course maintenance and the student's daily life.

Special guidance: It is normal for Course Designers to update dates on every assignment when a new term starts. If most or all assignment changes are date updates (due dates, availability, unlock/lock dates, or similar calendar shifts) across the course, include a short explanation that this is probably due to the beginning of a new semester. Do not treat that pattern as unusual or alarming.

Format your response exactly like this:
Impact: [Low/Medium/High]
Summary: [Your 2-4 sentence summary]
"""
        text = _generate_content(api_key, prompt)
        
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


def summarize_category_changes(category_title: str, file_summaries: list) -> str:
    """
    Uses Gemini API to generate a short category-level summary from file change summaries.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "AI Summarization disabled: GEMINI_API_KEY not found in environment."

    if not file_summaries:
        return ""

    usable = [
        s for s in file_summaries
        if s and not s.startswith("AI Summarization disabled") and not s.startswith("AI Summarization failed")
    ]
    if not usable:
        return ""

    if len(usable) == 1:
        return usable[0]

    try:
        summaries_text = "\n".join([f"- {s}" for s in usable])

        prompt = f"""
You are an expert Course Designer and Canvas LMS administrator.
Analyze these individual file changes within the "{category_title}" category of a Canvas course.

Individual Changes:
{summaries_text}

Provide a very short, direct 1-3 sentence summary of what changed overall in this category.
Focus on the pattern and student/teacher impact. Do not list every file.
Special guidance: If most or all changes are assignment date updates (due dates, availability, unlock/lock dates), briefly note this is probably due to the beginning of a new semester.
Be extremely direct and avoid conversational filler.
"""
        return _generate_content(api_key, prompt)
    except Exception as e:
        return f"AI Summarization failed: {e}"
