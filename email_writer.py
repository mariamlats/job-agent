"""
email_writer.py (v4) - Truly personalised using actual job descriptions
"""

import os
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv
from config import CANDIDATE, SALARY

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"


def _pick_best_project(job_title, company, industry="", description=""):
    text = (job_title + " " + industry + " " + company + " " + description).lower()
    best, best_score = None, 0
    for project in CANDIDATE["projects"]:
        score = sum(1 for kw in project["relevant_for"] if kw.lower() in text)
        if score > best_score:
            best_score, best = score, project
    return best or CANDIDATE["projects"][0]


def _make_subject(job, is_cold):
    title = job.get("title", "")
    company = job.get("company", "your team")
    name = CANDIDATE["name"]
    if is_cold or title in ("Cold Outreach", ""):
        return f"Exploring Opportunities at {company} — {name} | AI Engineer"
    return f"Application: {title} — {name}"


def _build_prompt(job, is_cold):
    title = job.get("title", "AI/Software Engineer")
    company = job.get("company", "your company")
    description = job.get("description", "")
    company_info = job.get("company_info", "")
    location = job.get("location", "Remote/Italy")
    if title == "Cold Outreach":
        title = "AI Engineer / Software Engineer"

    project = _pick_best_project(title, company, job.get("industry",""), description)

    context_lines = []
    if description:
        context_lines.append(f"JOB DESCRIPTION:\n{description[:600]}")
    if company_info:
        context_lines.append(f"ABOUT THE COMPANY:\n{company_info[:300]}")
    context_section = "\n\n".join(context_lines) if context_lines else ""

    salary_note = ""
    if SALARY["mention_flexible_salary"]:
        salary_note = f'\nInclude near end: "{SALARY["flexible_salary_line"]}"'

    type_line = (
        f"COLD OUTREACH to {company} — no specific job posted, ask if openings exist."
        if is_cold else
        f"APPLICATION for: {title} at {company}."
    )

    personalisation_note = (
        "\n\nIMPORTANT: The job description above contains specific details. "
        "Reference at least ONE specific thing from it (a technology, a product, "
        "a requirement, or what the company does). "
        "This email must feel hand-written for THIS company, not copy-pasted."
        if context_section else
        "\n\nNo job description available — write a strong general application."
    )

    return f"""Write a professional, personalised job application email for {CANDIDATE['name']}.

TYPE: {type_line}

{context_section}{personalisation_note}

CANDIDATE:
- {CANDIDATE['name']}, Rome, Italy
- {CANDIDATE['education']}
- {CANDIDATE['summary']}
- GitHub: {CANDIDATE['github']} | LinkedIn: {CANDIDATE['linkedin']}

BEST PROJECT TO MENTION:
- {project['name']}: {project['description']}
- Tech: {', '.join(project['tech'])} | {project['url']}

RULES:
- 3 paragraphs, 150-200 words
- Para 1: Hook — name company, reference something SPECIFIC about them
- Para 2: ONE achievement tied to THEIR specific need
- Para 3: CTA, mention CV attached
- British English. No buzzwords. Sound human.
- Don't start with "I am writing to..."{salary_note}

OUTPUT FORMAT ONLY:
SUBJECT: [subject]
---
[email body]
"""


def _call_gemini(prompt):
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.8, max_output_tokens=500),
    )
    return response.text.strip()


def _parse(text, fallback_subject):
    subject, body_lines, parsing = "", [], False
    for line in text.split("\n"):
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
        elif line.strip() == "---":
            parsing = True
        elif parsing:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return subject or fallback_subject, body or text


def write_email(job, is_cold_outreach=False):
    is_cold = (is_cold_outreach or
               job.get("platform") == "cold_outreach" or
               job.get("title") == "Cold Outreach")
    fallback_subject = _make_subject(job, is_cold)
    project = _pick_best_project(
        job.get("title",""), job.get("company",""),
        job.get("industry",""), job.get("description","")
    )
    try:
        text = _call_gemini(_build_prompt(job, is_cold))
        subject, body = _parse(text, fallback_subject)
        return {"subject": subject, "body": body, "project_used": project["name"], "is_cold": is_cold}
    except Exception as e:
        print(f"[email_writer] Gemini error: {e}")
        company = job.get("company", "Hiring Team")
        title = job.get("title", "AI Engineer")
        if title == "Cold Outreach":
            title = "AI Engineer / Software Engineer"
        return {
            "subject": fallback_subject,
            "body": (
                f"Dear {company} team,\n\n"
                f"I came across {company} and was drawn to your work. "
                f"I'm {CANDIDATE['name']}, an AI Engineer based in Rome. "
                f"I built a WiFi-based tumour detection system (AUC 0.92) for my "
                f"Bachelor's thesis at Sapienza, and deployed a production invoice "
                f"automation system cutting processing time 16x.\n\n"
                f"I'd love to explore a {title} role. CV attached — open to a brief call?\n\n"
                f"Best,\n{CANDIDATE['name']}\n{CANDIDATE['email']} | {CANDIDATE['linkedin']}"
            ),
            "project_used": project["name"],
            "is_cold": is_cold,
        }


def write_followup_email(original_app):
    prompt = f"""Brief follow-up. No reply to application sent ~1 week ago.
Company: {original_app.get('company')} | Role: {original_app.get('role')}
Max 2 paragraphs, under 80 words. Polite, not pushy. Simple CTA.
FORMAT:
SUBJECT: [subject]
---
[body]
"""
    try:
        text = _call_gemini(prompt)
        subject, body = _parse(text, f"Following up — {original_app.get('role')}")
        return {"subject": subject, "body": body, "is_followup": True}
    except:
        return {
            "subject": f"Following up — {original_app.get('role')}",
            "body": (
                f"Dear {original_app.get('company')} team,\n\n"
                f"Following up on my application for {original_app.get('role')} sent last week. "
                f"Still very interested — would love to connect.\n\n"
                f"Best,\n{CANDIDATE['name']}"
            ),
            "is_followup": True,
        }


if __name__ == "__main__":
    test_job = {
        "title": "Junior AI Engineer",
        "company": "Empatica",
        "platform": "linkedin",
        "location": "Milan / Remote",
        "description": (
            "Empatica builds medical-grade wearables for epilepsy monitoring. "
            "Looking for AI engineer for seizure detection algorithms using biosignal "
            "data from E4 wristband. Work with Python, TensorFlow, time-series data. "
            "Signal processing and anomaly detection experience a plus."
        ),
        "company_info": "Empatica develops clinical-grade wearable sensors for healthcare.",
    }
    result = write_email(test_job)
    print(f"Subject: {result['subject']}")
    print(f"Project used: {result['project_used']}")
    print("---")
    print(result["body"])
