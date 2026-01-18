import os
import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def add_ngrok_skip_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX_ID = os.getenv("GOOGLE_CX_ID")


def search_news_logic(query):
    if not NAVER_ID: return "에러: 네이버 API 키 미설정"
    try:
        url = f"https://openapi.naver.com/v1/search/news.json?query={query} 팩트체크&display=10&sort=sim"
        headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
        res = requests.get(url, headers=headers).json()
        items = res.get('items', [])
        
        if not items:
            return "❌ 검색 결과 없음: 해당 키워드와 관련된 공신력 있는 보도를 찾을 수 없습니다."

        md = f"### [실시간 뉴스 팩트체크 근거 자료]\n"
        for idx, i in enumerate(items, 1):
            t = i['title'].replace('<b>','').replace('</b>','').replace('&quot;', '"')
            d = i['description'].replace('<b>','').replace('</b>','').replace('&quot;', '"')
            md += f"{idx}. **출처**: {t}\n   - **보도 내용**: {d}\n\n"
        
        md += "---\n*지시: 위 보도 내용들의 일관성을 확인하여 사실 여부를 판정하고, 상충되는 내용이 있다면 함께 언급하세요.*"
        return md
    except Exception as e: return f"뉴스 분석 에러: {str(e)}"

def search_google_logic(query, site_filter, title_name):
    if not GOOGLE_API_KEY: return "에러: 구글 API 키 미설정"
    try:
        search_query = f"{site_filter} {query}"
        url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={GOOGLE_CX_ID}&q={search_query}"
        res = requests.get(url).json()
        items = res.get('items', [])
        
        if not items: return f"❌ {title_name} 내에 관련 공식 기록이나 문서가 존재하지 않습니다."

        md = f"### [{title_name} 공식 문서 데이터]\n"
        for idx, i in enumerate(items[:5], 1):
            title = i['title'].replace('&quot;', '"')
            snippet = i.get('snippet', '').replace('\n', ' ')
            md += f"{idx}. **문서명**: {title}\n   - **상세 내용**: {snippet}\n\n"
        return md
    except Exception as e: return f"기관 데이터 검색 에러: {str(e)}"

# --- [MCP 인터페이스 규격: 답변 형식 강제 버전] ---
MCP_INFO = {
    "protocolVersion": "2025-03-26",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "FactCheck-Pro-Server", "version": "2.2.0"},
    "tools": [
        {
            "name": "search_news_fact",
            "description": (
                "실시간 뉴스 및 팩트체크 보도를 검색합니다. "
                "결과를 출력할 때 반드시 다음 형식을 엄격히 지키세요:\n"
                "판정: (진실 / 대체로 진실 / 거짓 / 판단 유보 중 선택)\n"
                "근거: (수집된 데이터를 바탕으로 논리적인 설명 작성)"
            ),
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        },
        {
            "name": "query_public_data",
            "description": (
                "정부 공식 자료를 검색합니다. "
                "결과를 출력할 때 반드시 다음 형식을 엄격히 지키세요:\n"
                "판정: (진실 / 대체로 진실 / 거짓 / 판단 유보 중 선택)\n"
                "근거: (공식 문서의 내용을 바탕으로 논리적인 설명 작성)"
            ),
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        },
        {
            "name": "verify_rumor_db",
            "description": (
                "전문 팩트체크 DB를 검색합니다. "
                "결과를 출력할 때 반드시 다음 형식을 엄격히 지키세요:\n"
                "판정: (진실 / 대체로 진실 / 거짓 / 판단 유보 중 선택)\n"
                "근거: (검증된 기록을 바탕으로 논리적인 설명 작성)"
            ),
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        }
    ]
}

@app.api_route("/", methods=["GET", "POST"])
async def mcp_interface(request: Request):
    if request.method == "GET": return MCP_INFO
    try:
        body = await request.json()
        req_id, method = body.get("id"), body.get("method")

        if method in ["initialize", "tools/list"]:
            return {"jsonrpc": "2.0", "id": req_id, "result": MCP_INFO}

        if method == "tools/call":
            params = body.get("params", {})
            tool_name = params.get("name")
            args = params.get("arguments", {})
            query = args.get("query", "")

            if tool_name == "search_news_fact":
                result_text = search_news_logic(query)
            elif tool_name == "query_public_data":
                result_text = search_google_logic(query, "site:go.kr", "정부 공식 자료")
            elif tool_name == "verify_rumor_db":
                result_text = search_google_logic(query, "site:factcheck.snu.ac.kr", "전문 팩트체크 DB")
            else:
                result_text = "알 수 없는 도구입니다."

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": result_text}]}
            }
    except Exception as e:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)