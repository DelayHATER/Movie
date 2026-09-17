import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------
# 배포 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 서버의 현재 시간을 그대로 사용하지 않고 KST를 사용합니다.

kst = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(kst).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_dt = yesterday_kst.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {yesterday_kst.strftime('%Y년 %m월 %d일')} "
    f"(한국 시간 기준)"
)


# --------------------------------------------------
# 3. KOBIS API 호출 함수
# --------------------------------------------------
# ttl=3600 → 약 1시간 동안 같은 결과를 기억합니다.
# 따라서 같은 날짜를 다시 조회해도 API를 계속 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt, api_key):
    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생했는지 확인
        response.raise_for_status()

        # JSON 형태로 변환
        data = response.json()

        return data, None

    except requests.exceptions.RequestException as e:
        return None, f"API 요청에 실패했습니다.\n\n{e}"

    except ValueError:
        return None, "API에서 JSON 형식의 응답을 받지 못했습니다."


# --------------------------------------------------
# 4. Secrets에서 인증키 가져오기
# --------------------------------------------------
# Streamlit Cloud의 Secrets에 다음처럼 등록해야 합니다.
#
# KOBIS_KEY = "발급받은_인증키"
#
# 인증키를 코드에 직접 적지 않습니다.

try:
    api_key = st.secrets["KOBIS_KEY"]

except KeyError:
    st.error(
        "🔑 KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 **Settings → Secrets**에서 "
        "`KOBIS_KEY`가 등록되어 있는지 확인하세요."
    )
    st.stop()


# --------------------------------------------------
# 5. API 호출
# --------------------------------------------------

data, error = get_boxoffice(target_dt, api_key)


# 요청 자체가 실패한 경우
if error:
    st.error("❌ 박스오피스 정보를 가져오지 못했습니다.")
    st.warning(
        "다음 항목을 확인해 주세요.\n\n"
        "- 인터넷 연결 상태\n"
        "- KOBIS API 서버 상태\n"
        "- API 요청 주소\n"
        "- Streamlit Cloud의 네트워크 상태"
    )
    st.stop()


# --------------------------------------------------
# 6. KOBIS API의 오류(faultInfo) 확인
# --------------------------------------------------
# KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있습니다.
# 따라서 HTTP 상태코드만 확인하면 안 되고 faultInfo도 확인해야 합니다.

if "faultInfo" in data:
    fault_info = data["faultInfo"]

    error_message = fault_info.get(
        "message",
        "KOBIS API에서 오류를 반환했습니다."
    )

    st.error("❌ KOBIS API 오류")
    st.warning(
        f"오류 내용: {error_message}\n\n"
        "KOBIS 인증키가 정확한지 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 7. 박스오피스 결과 확인
# --------------------------------------------------

boxoffice_result = data.get("boxOfficeResult")

if not boxoffice_result:
    st.error("❌ 박스오피스 결과를 찾을 수 없습니다.")
    st.warning(
        "KOBIS API 응답 구조가 정상인지 확인해 주세요."
    )
    st.stop()


movie_list = boxoffice_result.get("dailyBoxOfficeList", [])


# 영화 목록이 비어 있는 경우
if not movie_list:
    st.warning(
        "🎬 해당 날짜의 영화 목록이 없습니다.\n\n"
        "다음 사항을 확인해 주세요.\n\n"
        "- 조회 날짜가 올바른지 확인\n"
        "- KOBIS에서 해당 날짜의 일일 박스오피스가 집계되었는지 확인\n"
        "- KOBIS API가 정상적으로 응답했는지 확인"
    )
    st.stop()


# --------------------------------------------------
# 8. 문자열로 받은 숫자를 실제 숫자로 변환
# --------------------------------------------------
# KOBIS API는 rank, audiCnt, audiAcc, scrnCnt 등을
# 문자열로 보내므로 int로 변환합니다.

movies = []

for movie in movie_list:
    movies.append({
        "순위": int(movie.get("rank", 0)),
        "영화명": movie.get("movieNm", ""),
        "개봉일": movie.get("openDt", ""),
        "관객수": int(movie.get("audiCnt", 0)),
        "누적관객": int(movie.get("audiAcc", 0)),
        "스크린수": int(movie.get("scrnCnt", 0)),
    })


# 순위 순서대로 정렬
movies.sort(key=lambda x: x["순위"])


# --------------------------------------------------
# 9. 1위 영화 정보
# --------------------------------------------------

first_movie = movies[0]

st.subheader(f"🥇 1위: {first_movie['영화명']}")

# 지표 카드 3개
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "어제 관객수",
        f"{first_movie['관객수']:,}명"
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['누적관객']:,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개"
    )


# --------------------------------------------------
# 10. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda x: x["관객수"],
    reverse=True
)[:5]

# 그래프용 데이터프레임 만들기
import pandas as pd

chart_data = pd.DataFrame({
    "영화명": [movie["영화명"] for movie in top5],
    "관객수": [movie["관객수"] for movie in top5]
})

# 영화명을 인덱스로 설정하면 막대그래프의 가로축에 표시됩니다.
chart_data = chart_data.set_index("영화명")

st.bar_chart(
    chart_data,
    y="관객수"
)


# --------------------------------------------------
# 11. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎥 전체 박스오피스")

table_data = pd.DataFrame(movies)

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d"
        ),
        "영화명": st.column_config.TextColumn(
            "영화명"
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일"
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명"
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명"
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개"
        ),
    }
)


# --------------------------------------------------
# 12. 데이터 기준 안내
# --------------------------------------------------

st.caption(
    f"KOBIS 일일 박스오피스 · 기준일 {target_dt} · "
    "한국 시간 기준"
)
