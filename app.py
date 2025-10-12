import streamlit as st
import shlex
import pandas as pd
from datetime import date, datetime

# 간소화된 스크립트에서 필요한 함수만 가져옵니다.
from 뉴스수집 import search_naver_news, resolve_dates

# --- Streamlit UI 설정 ---
st.set_page_config(page_title="뉴스 검색기", page_icon="📰", layout="wide")
st.title("📰 네이버 뉴스 검색")
st.write("키워드와 날짜를 입력하여 관련 네이버 뉴스 기사를 검색합니다.")

# --- 입력 폼 ---
with st.form(key="search_form"):
    keywords_input = st.text_input(
        "검색할 키워드",
        placeholder='예: AI "홍길동 회장"', 
        help='정확한 구문(phrase)을 검색하려면 큰따옴표("")로 묶어주세요. 예: "홍길동 회장"'
    )
    
    start_date_input = st.date_input(
        "시작일",
        value=date.today(),
        max_value=date.today(),
        help="검색할 뉴스의 시작 날짜를 선택하세요."
    )
    
    submitted = st.form_submit_button("검색 시작")

# --- 검색 로직 실행 ---
if submitted:
    if not keywords_input:
        st.error("키워드를 하나 이상 입력해주세요.")
    else:
        # shlex를 사용해 따옴표로 묶인 구문을 하나의 키워드로 인식
        keywords = shlex.split(keywords_input.strip())
        start_date, end_date = resolve_dates(start_date_input.strftime("%Y%m%d"))

        display_keywords = [f'"{k}"' if ' ' in k else k for k in keywords]
        st.info(f"키워드: {', '.join(display_keywords)} | 기간: {start_date} ~ {end_date}")

        results_by_keyword = {}
        total_count = 0
        with st.spinner("뉴스 기사를 검색하고 있습니다..."):
            for kw in keywords:
                results = search_naver_news(kw, start_date, end_date)
                if results:
                    # 중복 제거
                    unique_results = []
                    seen_links = set()
                    for item in results:
                        if item['link'] not in seen_links:
                            unique_results.append(item)
                            seen_links.add(item['link'])
                    results_by_keyword[kw] = unique_results
                    total_count += len(unique_results)
        
        if not results_by_keyword:
            st.warning("검색된 기사가 없습니다. 다른 키워드나 기간으로 시도해보세요.")
        else:
            st.success(f"총 {total_count}개의 기사를 찾았습니다.")
            st.divider()

            # 키워드별로 테이블 출력
            for keyword, items in results_by_keyword.items():
                st.subheader(f"'{keyword}' 검색 결과 ({len(items)}건)")
                df = pd.DataFrame(items)
                
                st.dataframe(
                    df,
                    column_config={
                        "title": st.column_config.TextColumn("제목", width="large"),
                        "link": st.column_config.LinkColumn("기사 링크", display_text="바로가기")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                st.write(" ") # 여백