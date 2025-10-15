import streamlit as st
import shlex
import pandas as pd
from datetime import date, datetime

# 간소화된 스크립트에서 필요한 함수만 가져옵니다.
from 뉴스수집 import search_naver_news, search_google_news, resolve_dates

# --- Streamlit UI 설정 ---
st.set_page_config(page_title="뉴스 검색", page_icon="📰", layout="wide")
st.title("📰 뉴스 검색")
st.write("키워드와 날짜를 입력하여 관련 뉴스 기사를 검색합니다.")

# --- 입력 폼 ---
with st.form(key="search_form"):
    search_engine = st.radio("검색 엔진 선택", ("네이버", "구글"), horizontal=True)
    keywords_input = st.text_input(
        "검색할 키워드",
        placeholder='예: AI "홍길동 회장"',
        help='정확한 구문(phrase)을 검색하려면 큰따옴표("")로 묶어주세요. 예: "홍길동 회장"'
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        start_date_input = st.date_input(
            "시작일",
            value=date.today(),
            max_value=date.today(),
            help="검색할 뉴스의 시작 날짜를 선택하세요."
        )
    with col2:
        end_date_input = st.date_input(
            "종료일",
            value=date.today(),
            max_value=date.today(),
            help="검색할 뉴스의 종료 날짜를 선택하세요."
        )
    with col3:
        max_articles_input = st.number_input(
            "최대 기사 수",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="검색할 최대 기사 수를 지정합니다."
        )

    submitted = st.form_submit_button("검색 시작")

# --- 검색 로직 실행 ---
if submitted:
    if not keywords_input:
        st.error("키워드를 하나 이상 입력해주세요.")
    else:
        # shlex를 사용해 따옴표로 묶인 구문을 하나의 키워드로 인식
        keywords = shlex.split(keywords_input.strip())
        start_date, end_date = resolve_dates(start_date_input.strftime("%Y%m%d"), end_date_input.strftime("%Y%m%d"))

        display_keywords = [f'"{k}"' if ' ' in k else k for k in keywords]
        st.info(f"키워드: {', '.join(display_keywords)} | 기간: {start_date} ~ {end_date} | 최대 {max_articles_input}개")

        results_by_keyword = {}
        total_count = 0
        with st.spinner("뉴스 기사를 검색하고 있습니다..."):
            for kw in keywords:
                if search_engine == "네이버":
                    results = search_naver_news(kw, start_date, end_date, max_items=max_articles_input)
                else: # 구글
                    # Google 날짜 형식(YYYY-MM-DD)에 맞게 변환
                    start_date_google = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
                    end_date_google = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
                    results = search_google_news(kw, start_date_google, end_date_google, max_items=max_articles_input)

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
                # 제목(title)과 링크(link)를 마크다운 링크 형식으로 합친 새 열 생성
                df['기사 제목'] = df.apply(lambda row: f"[{row['title']}]({row['link']})", axis=1)
                
                # 마크다운 테이블로 변환하여 출력
                st.markdown(
                    df[['기사 제목']].to_markdown(index=False),
                    unsafe_allow_html=True
                )
                st.write(" ") # 여백