# -*- coding: utf-8 -*-
"""
네이버 뉴스 검색기
- 키워드, 기간을 받아 검색 결과(제목, 링크) 목록을 반환
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urlparse
from datetime import datetime

# ---------------- 설정 ----------------
DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
SEARCH_BASE = "https://search.naver.com/search.naver"
SLEEP_BETWEEN_REQUESTS = 0.1
SEARCH_PAGES = 5  # 한 번에 더 많은 결과를 보여주기 위해 페이지 수 증가
MAX_PER_KEYWORD = 50

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
def search_naver_news(keyword: str, start_date: str, end_date: str, pages=SEARCH_PAGES, max_items=MAX_PER_KEYWORD):
    results, collected = [], 0
    for page in range(pages):
        params = {
            "where": "news",
            "sm": "tab_opt",
            "query": keyword,
            "start": page * 10 + 1,
            "nso": f"so:r,p:{start_date}to{end_date},a:all",
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
            print(f"Search request failed for URL {url}: {e}")
            break
            
    return results