"""
email_finder.py (v2) - Fixed: no longer uses job board URLs as company domains
"""

import os
import re
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from config import EMAIL_PATTERNS

load_dotenv()
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

JOB_BOARD_DOMAINS = {
    "linkedin.com", "indeed.com", "glassdoor.com", "welcometothejungle.com",
    "monster.com", "ziprecruiter.com", "lever.co", "greenhouse.io",
    "workday.com", "taleo.net", "icims.com", "jobvite.com", "jobvite.com",
}

def get_domain(url):
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    domain = urlparse(url).netloc.replace("www.", "").lower()
    for jb in JOB_BOARD_DOMAINS:
        if jb in domain:
            return ""
    return domain

def company_name_to_domain(name):
    name = name.lower().strip()
    for suffix in [" inc", " ltd", " llc", " gmbh", " srl", " spa", " s.r.l.", " s.p.a.", " ag", " bv"]:
        name = name.replace(suffix, "")
    name = re.sub(r"[^a-z0-9]", "", name)
    return f"{name}.com" if name else ""

def hunter_lookup(domain):
    if not HUNTER_API_KEY or not domain:
        return []
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 5},
            timeout=10,
        )
        data = resp.json()
        emails = []
        if "data" in data and "emails" in data["data"]:
            for entry in data["data"]["emails"]:
                email = entry.get("value", "")
                dept = entry.get("department", "")
                if dept and any(k in dept.lower() for k in ["hr", "recruit", "talent", "people"]):
                    emails.insert(0, email)
                elif email:
                    emails.append(email)
        return emails[:3]
    except Exception as e:
        print(f"[email_finder] Hunter error for {domain}: {e}")
        return []

def scrape_contact_email(company_url):
    if not company_url or not company_url.startswith("http"):
        return []
    emails = []
    pages = [
        company_url.rstrip("/") + "/contact",
        company_url.rstrip("/") + "/about",
        company_url.rstrip("/") + "/careers",
        company_url,
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0)"}
    for url in pages:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                if a["href"].startswith("mailto:"):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip()
                    if email and "@" in email and email not in emails:
                        emails.append(email)
            found = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", soup.get_text())
            for e in found:
                if e not in emails and not e.endswith((".png", ".jpg", ".gif")):
                    if not any(jb in e for jb in JOB_BOARD_DOMAINS):
                        emails.append(e)
            if emails:
                break
        except Exception:
            continue
    return emails[:3]

def guess_emails(domain):
    if not domain:
        return []
    return [p.format(domain=domain) for p in EMAIL_PATTERNS]

def find_email(company_name, company_url="", careers_url=""):
    # Get real company domain — reject job board URLs
    domain = ""
    for url in [company_url, careers_url]:
        domain = get_domain(url)
        if domain:
            break
    if not domain:
        domain = company_name_to_domain(company_name)

    result = {
        "company": company_name, "domain": domain,
        "verified": [], "scraped": [], "guessed": [],
        "best": "", "source": "",
    }

    if domain:
        result["verified"] = hunter_lookup(domain)
        result["scraped"] = scrape_contact_email(f"https://{domain}")
        result["guessed"] = guess_emails(domain)

    if result["verified"]:
        result["best"] = result["verified"][0]
        result["source"] = "hunter"
    elif result["scraped"]:
        for e in result["scraped"]:
            if not any(x in e.lower() for x in ["noreply", "no-reply", "donotreply"]):
                result["best"] = e
                result["source"] = "scraped"
                break
    elif result["guessed"]:
        result["best"] = result["guessed"][0]
        result["source"] = "guessed"

    return result

if __name__ == "__main__":
    result = find_email("Empatica", "https://www.empatica.com")
    print(f"Best: {result['best']} (source: {result['source']})")
    print(f"Domain guessed: {result['domain']}")
