"""
scorer.py
─────────
Ranks jobs by likelihood of getting hired, based on:
1. Role relevance — how well the title matches your profile
2. Company size fit — startups/mid-size more likely to hire entry-level
3. Tech stack match — how many of your skills appear in the description
4. Seniority fit — junior/entry-level roles score higher
5. Location fit — remote or Italy-based score higher
6. Industry fit — AI/healthtech/fintech score higher (your strongest projects)
7. Cold outreach penalty — direct postings score higher than cold outreach
"""

import re

# ── Weights (must sum to 1.0) ──────────────────────────────────────────────────
WEIGHTS = {
    "role_relevance":   0.25,
    "seniority_fit":    0.20,
    "tech_match":       0.20,
    "industry_fit":     0.15,
    "location_fit":     0.10,
    "source_bonus":     0.10,
}

# ── Role relevance keywords ────────────────────────────────────────────────────
ROLE_TIERS = {
    1.0: ["ai engineer", "machine learning engineer", "ml engineer", "deep learning engineer",
          "ai research engineer", "research engineer", "nlp engineer", "computer vision engineer"],
    0.8: ["data scientist", "junior ai", "junior ml", "backend engineer", "python developer",
          "software engineer", "junior software", "junior data"],
    0.6: ["data engineer", "full stack", "fullstack", "flask developer", "api developer"],
    0.4: ["developer", "programmer", "engineer", "analyst"],
}

# ── Seniority keywords ────────────────────────────────────────────────────────
JUNIOR_SIGNALS = ["junior", "entry", "entry-level", "graduate", "fresher",
                  "intern", "trainee", "0-2 years", "0-1 year", "1 year",
                  "no experience required", "recent graduate"]

SENIOR_PENALTIES = ["senior", "lead", "principal", "staff", "head of",
                    "5+ years", "7+ years", "8+ years", "10+ years"]

# ── Tech stack ────────────────────────────────────────────────────────────────
YOUR_SKILLS = ["python", "tensorflow", "keras", "scikit-learn", "flask",
               "postgresql", "supabase", "java", "c#", "swift", "git",
               "deep learning", "machine learning", "neural network",
               "rest api", "backend", "sql", "openCV", "mediapipe",
               "pytorch", "pandas", "numpy", "docker", "fastapi"]

# ── Industry fit ──────────────────────────────────────────────────────────────
INDUSTRY_SCORES = {
    1.0: ["healthtech", "medtech", "medical", "biotech", "health", "clinical",
          "cancer", "diagnostic", "ai", "machine learning", "deep learning",
          "anomaly detection", "research"],
    0.8: ["fintech", "finance", "banking", "payments", "insurtech",
          "saas", "startup", "scale-up", "tech"],
    0.6: ["logistics", "supply chain", "e-commerce", "retail", "marketing",
          "data", "analytics", "cloud"],
    0.4: ["consulting", "it services", "software", "digital"],
}

# ── Location fit ──────────────────────────────────────────────────────────────
LOCATION_SCORES = {
    1.0: ["remote", "fully remote", "remote-first"],
    0.9: ["italy", "rome", "milan", "bologna", "florence", "turin"],
    0.7: ["europe", "eu", "berlin", "paris", "amsterdam", "london",
          "barcelona", "lisbon", "stockholm"],
    0.3: ["india", "usa", "us", "united states", "canada", "australia"],
}

# ── Company size signals (from company name patterns) ─────────────────────────
STARTUP_SIGNALS = ["ai", "tech", "labs", "io", "ly", "fy", ".ai", "cloud",
                   "data", "intelligence", "analytics", "digital"]


def score_role_relevance(title: str) -> float:
    title_lower = title.lower()
    for score, keywords in ROLE_TIERS.items():
        if any(kw in title_lower for kw in keywords):
            return score
    return 0.2


def score_seniority_fit(title: str, description: str = "") -> float:
    text = (title + " " + description).lower()
    # Junior signals boost score
    junior_hits = sum(1 for s in JUNIOR_SIGNALS if s in text)
    # Senior signals reduce score
    senior_hits = sum(1 for s in SENIOR_PENALTIES if s in text)
    if senior_hits > 0:
        return max(0.1, 0.5 - (senior_hits * 0.15))
    if junior_hits > 0:
        return min(1.0, 0.7 + (junior_hits * 0.1))
    return 0.6  # Neutral — no seniority signal


def score_tech_match(description: str) -> float:
    if not description:
        return 0.5  # No description — assume neutral
    desc_lower = description.lower()
    hits = sum(1 for skill in YOUR_SKILLS if skill in desc_lower)
    # Normalise: 5+ hits = 1.0, 0 hits = 0.2
    return min(1.0, 0.2 + (hits * 0.12))


def score_industry_fit(title: str, company: str, description: str = "") -> float:
    text = (title + " " + company + " " + description).lower()
    for score, keywords in INDUSTRY_SCORES.items():
        if any(kw in text for kw in keywords):
            return score
    return 0.3


def score_location_fit(location: str) -> float:
    if not location:
        return 0.6  # Unknown — assume could be remote
    loc_lower = location.lower()
    for score, keywords in LOCATION_SCORES.items():
        if any(kw in loc_lower for kw in keywords):
            return score
    return 0.5


def score_source_bonus(platform: str) -> float:
    """Active job postings score higher than cold outreach."""
    if platform == "cold_outreach":
        return 0.3
    elif platform in ("linkedin", "indeed", "wttj"):
        return 1.0
    elif platform == "company_page":
        return 0.8
    return 0.6


def rank_job(job: dict) -> float:
    """
    Calculate a final hire-likelihood score for a job.
    Returns 0.0-1.0. Higher = more likely to get hired.
    """
    title = job.get("title", "")
    company = job.get("company", "")
    description = job.get("description", "")
    location = job.get("location", "")
    platform = job.get("platform", "")

    scores = {
        "role_relevance": score_role_relevance(title),
        "seniority_fit":  score_seniority_fit(title, description),
        "tech_match":     score_tech_match(description),
        "industry_fit":   score_industry_fit(title, company, description),
        "location_fit":   score_location_fit(location),
        "source_bonus":   score_source_bonus(platform),
    }

    final = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(final, 4)


def rank_jobs(jobs: list) -> list:
    """
    Rank a list of jobs by hire likelihood.
    Returns sorted list with 'hire_score' added to each job.
    """
    for job in jobs:
        job["hire_score"] = rank_job(job)
    return sorted(jobs, key=lambda x: x["hire_score"], reverse=True)


def explain_score(job: dict) -> str:
    """Human-readable score breakdown for a job."""
    title = job.get("title", "")
    company = job.get("company", "")
    description = job.get("description", "")
    location = job.get("location", "")
    platform = job.get("platform", "")

    breakdown = {
        "Role relevance":  score_role_relevance(title),
        "Seniority fit":   score_seniority_fit(title, description),
        "Tech match":      score_tech_match(description),
        "Industry fit":    score_industry_fit(title, company, description),
        "Location fit":    score_location_fit(location),
        "Source quality":  score_source_bonus(platform),
    }

    lines = [f"  {k}: {v:.2f}" for k, v in breakdown.items()]
    total = job.get("hire_score", rank_job(job))
    lines.append(f"  ─────────────")
    lines.append(f"  TOTAL: {total:.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    test_jobs = [
        {"title": "Junior AI Engineer", "company": "Empatica", "location": "Milan / Remote",
         "platform": "linkedin", "description": "python tensorflow deep learning healthtech"},
        {"title": "Senior Software Engineer", "company": "IBM", "location": "Rome",
         "platform": "cold_outreach", "description": "java enterprise 10 years experience"},
        {"title": "Machine Learning Engineer", "company": "Clearbox AI", "location": "Remote",
         "platform": "company_page", "description": "python scikit-learn anomaly detection"},
        {"title": "Python Developer", "company": "Joveo AI", "location": "India",
         "platform": "linkedin", "description": "python backend"},
        {"title": "AI Research Engineer", "company": "Mistral AI", "location": "Paris / Remote",
         "platform": "linkedin", "description": "deep learning pytorch research nlp"},
    ]

    ranked = rank_jobs(test_jobs)
    print("Jobs ranked by hire likelihood:\n")
    for i, job in enumerate(ranked, 1):
        print(f"{i}. [{job['hire_score']:.2f}] {job['title']} @ {job['company']}")
        print(explain_score(job))
        print()
