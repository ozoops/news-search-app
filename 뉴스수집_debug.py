# -*- coding: utf-8 -*-
"""
네이버 뉴스 검색기
- 키워드, 기간을 받아 검색 결과(제목, 링크) 목록을 반환
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urlparse, urljoin, parse_qs
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import sys

# ---------------- 설정 ----------------
DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
SEARCH_BASE = "https://search.naver.com/search.naver"
SLEEP_BETWEEN_REQUESTS = 0.1
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
GOOGLE_NEWS_HTML = "https://www.google.com/search"


def _safe_console_text(value) -> str:
    text = value if isinstance(value, str) else str(value)
    encoding = getattr(sys.stdout, "encoding", None)
    if not encoding:
        return text
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    return text


def safe_print(value) -> None:
    print(_safe_console_text(value))

# ---------------- 유틸 ----------------
def validate_yyyymmdd(s: str) -> None:
    if not re.fullmatch(r"\d{8}", s or ""):
        raise ValueError("날짜는 YYYYMMDD 형식이어야 합니다.")
    datetime.strptime(s, "%Y%m%d")

def resolve_dates(start: str = None, end: str = None):
    today = datetime.today().strftime("%Y%m%d")
    if start and not end:
        validate_yyyymmdd(start)
        end = today
    elif not start and not end:
        start, end = today, today
    else:
        validate_yyyymmdd(start)
        validate_yyyymmdd(end)
    if start > end:
        raise ValueError("시작일이 종료일보다 클 수 없습니다.")
    return start, end

def safe_get(url: str, headers=None, timeout=12, referer=None):
    headers = (headers or {}).copy()
    if referer:
        headers["Referer"] = referer
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r

def _format_naver_date_for_params(date_str: str) -> str:
    return f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"

def _clean_google_link(link: str) -> str:
    if not link:
        return link
    if link.startswith("/url?") or link.startswith("https://www.google.com/url?"):
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        target = query.get("q") or query.get("url")
        if target:
            return target[0]
        return urljoin("https://www.google.com", link)
    if link.startswith("http"):
        return link
    return urljoin("https://news.google.com", link)

def _parse_pub_date(pub_text: str):
    if not pub_text:
        return None
    try:
        dt = parsedate_to_datetime(pub_text)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.date()


# ---------------- 검색 결과 파싱 ----------------
def parse_search_results(html: str):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # 전략 1: 클래식 뉴스 아이템 (a.news_tit)
    for a_tag in soup.select("a.news_tit"):
        title = a_tag.get("title") or a_tag.get_text(strip=True)
        link = a_tag.get("href")
        if title and link:
            results.append({"title": title, "link": link})

    # 전략 2: 새로운 SDS 컴포넌트 아이템
    for span_tag in soup.select("span.sds-comps-text-type-headline1"):
        title = span_tag.get_text(strip=True)
        # 부모 태그에서 a 링크를 찾음
        a_tag = span_tag.find_parent("a")
        if a_tag:
            link = a_tag.get("href")
            if title and link:
                results.append({"title": title, "link": link})

    # 중복 제거 및 유효성 검사
    out, seen = [], set()
    for it in results:
        if it.get("link") and it["link"].startswith("http") and it["link"] not in seen:
            seen.add(it["link"])
            out.append(it)
            
    return out

# ---------------- 네이버 뉴스 검색 ----------------
def search_naver_news(keyword: str, start_date: str, end_date: str, max_items=100):
    results, collected = [], 0
    pages = (max_items + 9) // 10 # 페이지당 10개 결과
    start_ds = _format_naver_date_for_params(start_date)
    end_ds = _format_naver_date_for_params(end_date)

    for page in range(pages):
        params = {
            "where": "news",
            "sm": "tab_opt",
            "query": keyword,
            "start": page * 10 + 1,
            "nso": f"so:r,p:from{start_date}to{end_date},a:all",
            "pd": "3",
            "ds": start_ds,
            "de": end_ds,
        }
        url = SEARCH_BASE + "?" + urlencode(params)
        
        try:
            r = safe_get(url, headers=DEFAULT_HEADERS)
            items = parse_search_results(r.text)
            if not items:
                break
            
            for it in items:
                results.append(it)
                collected += 1
                if collected >= max_items:
                    return results
            
            if page < pages - 1:
                time.sleep(SLEEP_BETWEEN_REQUESTS)

        except requests.RequestException as e:
            safe_print(f"Search request failed for URL {url}: {e}")
            break
            
    return results

# ---------------- 구글 뉴스 검색 ----------------
def search_google_news(keyword: str, start_date: str, end_date: str, max_items=100):
    results = []

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        safe_print("Invalid date format for Google News search. Expect YYYY-MM-DD.")
        return results

    inclusive_end = (end_dt + timedelta(days=1)).isoformat()
    query = f'{keyword} after:{start_dt.isoformat()} before:{inclusive_end}'

    params = {
        "q": query,
        "hl": "ko",
        "gl": "KR",
        "ceid": "KR:ko",
    }
    url = GOOGLE_NEWS_RSS + "?" + urlencode(params)

    try:
        r = safe_get(url, headers=DEFAULT_HEADERS)
    except requests.RequestException as e:
        safe_print(f"Google search request failed for URL {url}: {e}")
        return _search_google_news_html(keyword, start_dt, end_dt, max_items)

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        safe_print(f"Failed to parse Google News RSS feed: {e}")
        return _search_google_news_html(keyword, start_dt, end_dt, max_items)

    seen_links = set()
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue

        pub_date = _parse_pub_date(item.findtext("pubDate"))
        if pub_date and (pub_date < start_dt or pub_date > end_dt):
            continue

        cleaned_link = _clean_google_link(link) or link
        if cleaned_link in seen_links:
            continue
        seen_links.add(cleaned_link)

        results.append({"title": title, "link": cleaned_link})
        if len(results) >= max_items:
            break

    if results:
        return results

    fallback = _search_google_news_html(keyword, start_dt, end_dt, max_items)
    if fallback:
        safe_print(f"Google RSS feed empty; HTML fallback returned {len(fallback)} articles.")
    else:
        safe_print("Google RSS feed returned no articles; HTML fallback also returned none.")
    return fallback


def _search_google_news_html(keyword, start_dt, end_dt, max_items):
    params = {
        "q": keyword,
        "tbm": "nws",
        "hl": "ko",
        "gl": "KR",
        "num": min(max_items, 100),
        "tbs": f"cdr:1,cd_min:{start_dt.isoformat()},cd_max:{end_dt.isoformat()}",
        "gbv": "1",
    }
    url = GOOGLE_NEWS_HTML + "?" + urlencode(params)

    try:
        r = safe_get(url, headers=DEFAULT_HEADERS)
    except requests.RequestException as e:
        safe_print(f"Google HTML fallback failed for URL {url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    anchor_selector = "a[href^='/url?'], a[href^='https://www.google.com/url?']"
    anchors = soup.select(anchor_selector)
    fallback_results = []
    seen = set()

    for a_tag in anchors:
        title = a_tag.get_text(" ", strip=True)
        if not title:
            continue
        link = _clean_google_link(a_tag.get("href"))
        if not link or link in seen:
            continue
        if link.startswith("https://maps.google.com") or "support.google.com" in link:
            continue
        seen.add(link)
        fallback_results.append({"title": title, "link": link})
        if len(fallback_results) >= max_items:
            break

    if not fallback_results:
        safe_print("Google HTML fallback returned no articles.")

    return fallback_results
