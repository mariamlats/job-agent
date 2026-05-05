"""
scraper.py (v4) - Fetches actual job descriptions for personalised emails
"""

import hashlib, re, time, asyncio, requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from langdetect import detect, LangDetectException
from config import JOB_TARGETS, CANDIDATE

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def make_job_id(title, company, url=""):
    return hashlib.md5(f"{title.lower().strip()}_{company.lower().strip()}_{url}".encode()).hexdigest()[:16]

def is_english(text):
    if not text or len(text) < 20:
        return True
    try:
        return detect(text[:500]) == "en"
    except LangDetectException:
        return True

def score_job(title, description=""):
    score = 0.0
    text = (title + " " + description).lower()
    for role in JOB_TARGETS["roles"]:
        if role.lower() in text:
            score += 0.3
            break
    score += min(sum(1 for kw in JOB_TARGETS["keywords_required"] if kw.lower() in text) * 0.05, 0.3)
    score += min(sum(1 for skill in CANDIDATE["key_skills"] if skill.lower() in text) * 0.04, 0.2)
    for kw in JOB_TARGETS["keywords_exclude"]:
        if kw.lower() in text:
            score -= 0.2
    if not is_english(title + " " + description[:200]):
        score -= 0.5
    return max(0.0, min(1.0, score))

def is_relevant(title, description=""):
    if JOB_TARGETS["english_only"] and not is_english(title + " " + description[:300]):
        return False
    return score_job(title, description) >= 0.2

def make_job(title, company, location, url, platform, description="", salary=""):
    return {"job_id": make_job_id(title, company, url), "title": title, "company": company,
            "location": location, "url": url, "platform": platform, "description": description,
            "salary": salary, "language": "en", "score": score_job(title, description),
            "company_info": ""}


def fetch_job_description(url, platform):
    """Fetch actual job description from posting URL."""
    if not url or not url.startswith("http") or platform == "cold_outreach":
        return ""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        desc_text = ""
        if "linkedin.com" in url:
            el = soup.find("div", class_=re.compile(r"description|show-more-less", re.I))
            if el:
                desc_text = el.get_text(separator=" ", strip=True)
        elif "indeed.com" in url:
            el = soup.find("div", id=re.compile(r"jobDescriptionText", re.I))
            if el:
                desc_text = el.get_text(separator=" ", strip=True)
        if not desc_text:
            candidates = [tag.get_text(separator=" ", strip=True)
                         for tag in soup.find_all(["div", "section", "article"])
                         if 200 < len(tag.get_text(strip=True)) < 5000]
            if candidates:
                desc_text = max(candidates, key=len)
        if desc_text:
            return re.sub(r"\s+", " ", desc_text).strip()[:700]
    except Exception:
        pass
    return ""


def fetch_company_info(company_url):
    """Get brief description of what company does."""
    if not company_url or not company_url.startswith("http"):
        return ""
    try:
        resp = requests.get(company_url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"][:400]
        for sel in ["#about", ".about", ".mission", "h1"]:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(strip=True)
                if 30 < len(t) < 400:
                    return t
    except Exception:
        pass
    return ""


async def scrape_indeed(query="AI engineer", location="Italy"):
    jobs = []
    url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&lang=en"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context(user_agent=HEADERS["User-Agent"], locale="en-US")).new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            for card in await page.query_selector_all("[data-testid='slider_item'], .job_seen_beacon"):
                try:
                    te = await card.query_selector("h2.jobTitle, [data-testid='jobTitle']")
                    ce = await card.query_selector("[data-testid='company-name'], .companyName")
                    le = await card.query_selector("[data-testid='text-location'], .companyLocation")
                    ae = await card.query_selector("a[href]")
                    title = (await te.inner_text()).strip() if te else ""
                    company = (await ce.inner_text()).strip() if ce else ""
                    loc = (await le.inner_text()).strip() if le else ""
                    href = await ae.get_attribute("href") if ae else ""
                    job_url = f"https://www.indeed.com{href}" if href and href.startswith("/") else href
                    if title and company and is_relevant(title):
                        jobs.append(make_job(title, company, loc, job_url or url, "indeed"))
                except Exception:
                    continue
            await browser.close()
    except Exception as e:
        print(f"[scraper] Indeed error: {e}")
    print(f"[scraper] Indeed ({query}): {len(jobs)} jobs")
    return jobs


async def scrape_linkedin(query="AI engineer", location="Italy"):
    jobs = []
    url = f"https://www.linkedin.com/jobs/search/?keywords={query.replace(' ', '%20')}&location={location.replace(' ', '%20')}&f_TPR=r86400"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context(user_agent=HEADERS["User-Agent"], locale="en-US")).new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            for card in await page.query_selector_all(".job-search-card, .base-card"):
                try:
                    te = await card.query_selector("h3.base-search-card__title")
                    ce = await card.query_selector("h4.base-search-card__subtitle")
                    le = await card.query_selector(".job-search-card__location")
                    ae = await card.query_selector("a.base-card__full-link")
                    title = (await te.inner_text()).strip() if te else ""
                    company = (await ce.inner_text()).strip() if ce else ""
                    loc = (await le.inner_text()).strip() if le else ""
                    href = await ae.get_attribute("href") if ae else ""
                    if title and company and is_relevant(title):
                        jobs.append(make_job(title, company, loc, href or url, "linkedin"))
                except Exception:
                    continue
            await browser.close()
    except Exception as e:
        print(f"[scraper] LinkedIn error: {e}")
    print(f"[scraper] LinkedIn ({query}): {len(jobs)} jobs")
    return jobs


async def scrape_wttj(query="AI engineer"):
    jobs = []
    url = f"https://www.welcometothejungle.com/en/jobs?query={query.replace(' ', '%20')}&page=1"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context(user_agent=HEADERS["User-Agent"], locale="en-US")).new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            for card in await page.query_selector_all("li[data-testid]"):
                try:
                    te = await card.query_selector("h4, h3")
                    ce = await card.query_selector("span[class*='company'], p[class*='company']")
                    ae = await card.query_selector("a[href]")
                    title = (await te.inner_text()).strip() if te else ""
                    company = (await ce.inner_text()).strip() if ce else ""
                    href = await ae.get_attribute("href") if ae else ""
                    job_url = f"https://www.welcometothejungle.com{href}" if href and href.startswith("/") else href
                    if title and company and is_relevant(title):
                        jobs.append(make_job(title, company, "Europe", job_url or url, "wttj"))
                except Exception:
                    continue
            await browser.close()
    except Exception as e:
        print(f"[scraper] WTTJ error: {e}")
    print(f"[scraper] WTTJ ({query}): {len(jobs)} jobs")
    return jobs


def scrape_company_career_page(company, careers_url, website=""):
    if not careers_url or not careers_url.startswith("http"):
        job = make_job("Cold Outreach", company, "", careers_url or "", "cold_outreach")
        if website:
            job["company_info"] = fetch_company_info(website)
        return [job]
    jobs = []
    try:
        resp = requests.get(careers_url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(resp.text, "lxml")
        elements = (
            soup.find_all("li", class_=re.compile(r"job|position|opening", re.I)) or
            soup.find_all("article", class_=re.compile(r"job|position", re.I)) or
            soup.find_all("div", class_=re.compile(r"job-card|position|opening|vacancy", re.I))
        )
        for el in elements[:15]:
            ae = el.find("a", href=True)
            te = el.find(["h2","h3","h4","span"], class_=re.compile(r"title|name|role", re.I))
            title = (te.get_text(strip=True) if te else ae.get_text(strip=True) if ae else "")
            if not title or len(title) < 5 or not is_relevant(title):
                continue
            href = ae["href"] if ae else ""
            if href.startswith("/"):
                from urllib.parse import urlparse
                base = f"{urlparse(careers_url).scheme}://{urlparse(careers_url).netloc}"
                href = base + href
            jobs.append(make_job(title, company, "", href or careers_url, "company_page"))
    except Exception as e:
        print(f"[scraper] Career page error for {company}: {e}")
    if not jobs:
        job = make_job("Cold Outreach", company, "", careers_url, "cold_outreach")
        if website:
            job["company_info"] = fetch_company_info(website)
        jobs.append(job)
    return jobs


def scrape_company_list(excel_path, max_companies=25):
    import openpyxl
    from pathlib import Path
    from datetime import datetime
    path = Path(excel_path).expanduser()
    if not path.exists():
        print(f"[scraper] Company list not found at {path}")
        return []
    wb = openpyxl.load_workbook(path)
    all_companies = []
    for row in wb.active.iter_rows(min_row=4, values_only=True):
        if row[1] and row[5]:
            all_companies.append({
                "name": str(row[1]),
                "careers_url": str(row[5]) if str(row[5]).startswith("http") else "",
                "website": str(row[7]) if row[7] and str(row[7]).startswith("http") else "",
            })
    day = datetime.now().timetuple().tm_yday
    start = (day * max_companies) % max(len(all_companies), 1)
    today = (all_companies[start:] + all_companies[:start])[:max_companies]
    jobs = []
    for c in today:
        print(f"[scraper] Checking {c['name']}...")
        jobs.extend(scrape_company_career_page(c["name"], c["careers_url"], c.get("website","")))
        time.sleep(1)
    print(f"[scraper] Company pages: {len(jobs)} entries")
    return jobs


def enrich_with_descriptions(jobs, max_fetch=35):
    """Fetch actual job descriptions for top active postings."""
    to_fetch = [j for j in jobs
                if j["platform"] not in ("cold_outreach",)
                and not j.get("description")
                and j.get("url","").startswith("http")][:max_fetch]
    if not to_fetch:
        return jobs
    print(f"[scraper] Fetching descriptions for {len(to_fetch)} jobs...")
    for job in to_fetch:
        desc = fetch_job_description(job["url"], job["platform"])
        if desc:
            job["description"] = desc
            job["score"] = score_job(job["title"], desc)
        time.sleep(0.5)
    return jobs


async def scrape_all_jobs(company_list_path=""):
    all_jobs, seen_ids = [], set()

    results = await asyncio.gather(
        scrape_indeed("AI engineer", "Italy"),
        scrape_indeed("machine learning engineer", "Remote Europe"),
        scrape_linkedin("AI engineer", "Italy"),
        scrape_linkedin("backend python engineer", "Remote"),
        scrape_wttj("AI engineer"),
        return_exceptions=True,
    )
    for batch in results:
        if isinstance(batch, Exception):
            print(f"[scraper] Batch error: {batch}")
            continue
        for j in batch:
            if j["job_id"] not in seen_ids:
                all_jobs.append(j)
                seen_ids.add(j["job_id"])

    if company_list_path:
        loop = asyncio.get_event_loop()
        for j in await loop.run_in_executor(None, scrape_company_list, company_list_path, 25):
            if j["job_id"] not in seen_ids:
                all_jobs.append(j)
                seen_ids.add(j["job_id"])

    all_jobs.sort(key=lambda x: x["score"], reverse=True)
    all_jobs = enrich_with_descriptions(all_jobs, max_fetch=35)
    all_jobs.sort(key=lambda x: x["score"], reverse=True)
    print(f"[scraper] Total: {len(all_jobs)} jobs")
    return all_jobs
