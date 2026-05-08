"""
config.py
âââââââââ
All your personal preferences, job targets, and agent settings in one place.
Edit this file to customise how the agent behaves.
"""

# ââ Candidate Profile âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
CANDIDATE = {
    "name": "Mariam Latsabidze",
    "email": "mlacabidze4@gmail.com",
    "phone": "+39 3472325673",
    "location": "Rome, Italy",
    "linkedin": "linkedin.com/in/mariamlats",
    "github": "github.com/mariamlats",
    "cv_path": "~/Desktop/Mariam_Latsabidze_CV_v5.docx",   # update if CV moves
    "summary": (
        "AI Engineer with a background in software development and deep learning research "
        "(107/110, Sapienza). Built a WiFi-based tumour detection system (AUC 0.92) for my "
        "Bachelor's thesis and deployed production software for real businesses â from anomaly "
        "detection models to full-stack web apps. Looking to apply ML and engineering skills "
        "in a hands-on role."
    ),
    "key_skills": [
        "Python", "TensorFlow", "Keras", "scikit-learn", "deep learning",
        "anomaly detection", "Flask", "Supabase", "PostgreSQL", "REST APIs",
        "Java", "C#", "Swift", "Git", "OpenCV", "MediaPipe",
    ],
    "projects": [
        {
            "name": "WiFi-Based Cancer Diagnostics",
            "description": "Non-invasive tumour detection using WiFi CSI signals and deep anomaly detection. Deep Matrix Autoencoder achieved AUC 0.92 on clinical hospital data.",
            "tech": ["Python", "TensorFlow", "scikit-learn"],
            "url": "github.com/mariamlats/WiFi-Based-Cancer-Diagnostics",
            "relevant_for": ["healthtech", "medtech", "AI", "research", "deep learning", "anomaly detection"],
        },
        {
            "name": "Invoice Management System",
            "description": "Multi-tenant invoice automation system in production. Reduced invoice generation from a full working day to 30 minutes â 16x improvement.",
            "tech": ["Flask", "Supabase", "PostgreSQL", "Render"],
            "url": "github.com/mariamlats/invoice-app",
            "relevant_for": ["backend", "SaaS", "logistics", "fintech", "full-stack"],
        },
        {
            "name": "Bitcoin Network Simulation",
            "description": "Full P2P Bitcoin network simulation: PoW mining, AES/RSA encryption, fork resolution, chain reorganisation.",
            "tech": ["Java"],
            "url": "github.com/mariamlats/Bitcoin-Simulation",
            "relevant_for": ["blockchain", "fintech", "distributed systems", "Java"],
        },
        {
            "name": "Computer Vision Hand Drawing App",
            "description": "Real-time gesture-controlled drawing application using hand landmark detection.",
            "tech": ["Python", "OpenCV", "MediaPipe"],
            "url": "github.com/Penny-03/Computer-Vision",
            "relevant_for": ["computer vision", "AI", "Python"],
        },
    ],
    "education": "BSc Applied CS & AI, Sapienza University of Rome (107/110). Currently MSc CS at Sapienza.",
    "languages": "English (fluent), Georgian (native), German (B2), Russian (B1), Italian (learning)",
    "open_to_relocation": True,
    "open_to_remote": True,
}

# ââ Salary / Compensation âââââââââââââââââââââââââââââââââââââââââââââââââââââ
SALARY = {
    # If True, apply to ALL jobs regardless of posted salary (priority = getting hired)
    "apply_regardless_of_salary": True,
    # Include a line about flexible/junior compensation in emails
    "mention_flexible_salary": True,
    "flexible_salary_line": (
        "I'm open to a compensation arrangement that reflects an entry-level position â "
        "my priority right now is gaining hands-on experience in a strong team."
    ),
}

# ââ Job Target Preferences âââââââââââââââââââââââââââââââââââââââââââââââââââââ
JOB_TARGETS = {
    "roles": [
        "AI Engineer", "Junior AI Engineer", "Machine Learning Engineer",
        "ML Engineer", "Backend Engineer", "Backend Developer",
        "Python Developer", "Research Engineer", "Data Scientist",
        "Software Engineer", "Deep Learning Engineer", "NLP Engineer",
        "Computer Vision Engineer", "AI Developer",
    ],
    "keywords_required": [
        "python", "machine learning", "AI", "deep learning", "backend",
        "flask", "tensorflow", "pytorch", "scikit-learn", "ML",
    ],
    "keywords_exclude": [
        # Skip these â not relevant or Italian-only
        "senior", "lead", "principal", "director", "manager",
        "10+ years", "8+ years", "7+ years",
    ],
    # CRITICAL â only English job postings
    "english_only": True,
    # Locations to target
    "locations": [
        "Rome", "Milan", "Italy", "Remote", "Europe", "EU",
        "Berlin", "Paris", "Amsterdam", "London", "Barcelona",
        "Lisbon", "Madrid", "Stockholm", "Helsinki", "Dublin",
    ],
    # Skip if job is clearly Italian-only (title or description in Italian)
    "skip_italian_only": True,
}

# ââ Platforms to Scrape âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
PLATFORMS = {
    "linkedin": True,
    "indeed": True,
    "glassdoor": True,
    "welcometothejungle": True,
    "otta": True,
    "company_career_pages": True,   # uses your Excel company list
}

# ââ Email Settings âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
EMAIL_SETTINGS = {
    "max_per_day": 30,
    # Randomise send times between these hours to avoid spam detection
    "send_window_start": 8,    # 8am
    "send_window_end": 18,     # 6pm
    # Min gap between sends (minutes) â avoids burst sending
    "min_gap_minutes": 15,
    # Follow up if no reply after this many days
    "followup_after_days": 7,
    # Max follow-ups per application
    "max_followups": 1,
    # Never apply to same company twice within this many days
    "cooldown_days": 30,
}

# ââ Email Patterns for Guessing âââââââââââââââââââââââââââââââââââââââââââââââ
# Used when Hunter.io doesn't find a direct email
EMAIL_PATTERNS = [
    "jobs@{domain}",
    "careers@{domain}",
    "hr@{domain}",
    "hiring@{domain}",
    "talent@{domain}",
    "recruiting@{domain}",
    "recruitment@{domain}",
    "info@{domain}",
    "hello@{domain}",
]

# ââ Company Excel File ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
COMPANY_LIST_PATH = str(Path(__file__).parent / "companies.xlsx")

# ââ Agent Schedule âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
SCHEDULE = {
    # Run the full job scan daily at this time
    "daily_scan_time": "08:00",
    # Send daily digest summary to Telegram at this time
    "digest_time": "09:00",
}
