import os
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("FactCheck-Master")

# API 환경 변수
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX_ID = os.getenv("GOOGLE_CX_ID")

# --- 유틸리티: 신뢰도 계산 및 포맷팅 ---
def calculate_trust_score(items, weight):
    """
    items: 검색 결과 리스트
    weight: 소스별 가중치 (정부/학술: 1.2, 뉴스: 0.8 등)
    """
    count = len(items)
    # 기본 점수: 검색 결과 1개당 25점 (최대 3개 기준), 가중치 적용
    base_score = min(count * 25 * weight, 100)
    
    if base_score >= 80:
        status = "🟢 신뢰도 높음"
    elif base_score >= 50:
        status = "🟡 신뢰도 보통"
    else:
        status = "🔴 신뢰도 낮음 (추가 확인 필요)"
    
    return int(base_score), status

def format_as_markdown(title, items, source_type, weight=1.0):
    score, status = calculate_trust_score(items, weight)
    
    md = f"## {status} ({score}점)\n"
    md += f"### 🔍 {title} ({source_type})\n"
    
    if not items:
        md += "- 관련된 공신력 있는 자료를 찾지 못했습니다.\n"
        return md
    
    for item in items:
        md += f"- **{item['title']}**\n  - {item['description']}\n"
    
    md += f"\n> *본 점수는 {source_type}의 검색 결과 수와 출처 가중치를 바탕으로 계산되었습니다.*"
    return md

# --- Tool 1: 뉴스 기반 팩트체크 (가중치 0.8) ---
@mcp.tool()
def search_news_fact(query: str) -> str:
    """언론사 뉴스를 검색하여 실시간 팩트체크 점수를 반환합니다."""
    url = f"https://openapi.naver.com/v1/search/news.json?query={query} 팩트체크&display=3"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    
    try:
        res = requests.get(url, headers=headers).json()
        items = [{"title": i['title'].replace('<b>','').replace('</b>',''), 
                  "description": i['description'].replace('<b>','').replace('</b>','')} 
                 for i in res.get('items', [])]
        return format_as_markdown("뉴스 실시간 검색", items, "언론사 뉴스", weight=0.8)
    except Exception as e:
        return f"뉴스 검색 오류: {str(e)}"

# --- Tool 2: 공공데이터/정부 보도자료 (가중치 1.2) ---
@mcp.tool()
def query_public_data(query: str) -> str:
    """정부 공식 자료를 검색하여 매우 높은 가중치의 신뢰도 점수를 반환합니다."""
    search_query = f"site:go.kr {query}"
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX_ID}&q={search_query}"
    
    try:
        res = requests.get(url).json()
        items = [{"title": i['title'], "description": i['snippet']} for i in res.get('items', [])[:3]]
        return format_as_markdown("정부 공식 자료", items, "공공기관", weight=1.2)
    except Exception as e:
        return f"공공데이터 조회 오류: {str(e)}"

# --- Tool 3: SNU 팩트체크/루머 DB (가중치 1.1) ---
@mcp.tool()
def verify_rumor_db(query: str) -> str:
    """기존 팩트체크 DB와 대조하여 신뢰도 점수를 반환합니다."""
    search_query = f"site:factcheck.snu.ac.kr OR site:kakaocorp.com {query}"
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX_ID}&q={search_query}"
    
    try:
        res = requests.get(url).json()
        items = [{"title": i['title'], "description": i['snippet']} for i in res.get('items', [])[:3]]
        return format_as_markdown("검증된 사례 대조", items, "팩트체크 DB", weight=1.1)
    except Exception as e:
        return f"루머 DB 검색 오류: {str(e)}"

# --- Tool 4: 학술 논문 및 과학적 근거 (가중치 1.3) ---
@mcp.tool()
def extract_scientific_paper(query: str) -> str:
    """학술 자료 및 논문을 검색하여 가장 높은 가중치의 신뢰도 점수를 반환합니다."""
    search_query = f"site:scholar.google.com OR site:ncbi.nlm.nih.gov {query}"
    url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX_ID}&q={search_query}"
    
    try:
        res = requests.get(url).json()
        items = [{"title": i['title'], "description": i['snippet']} for i in res.get('items', [])[:2]]
        return format_as_markdown("과학적 근거 분석", items, "학술 자료", weight=1.3)
    except Exception as e:
        return f"학술 자료 검색 오류: {str(e)}"

if __name__ == "__main__":
    mcp.run()