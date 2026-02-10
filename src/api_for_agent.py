# server.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# 앞서 저장한 봇 클래스 가져오기
from agent_for_mcp_fhir import ClinicalChatbot 

# =============================================================================
# 1. 전역 변수 및 Lifespan (서버 수명 주기 관리)
# =============================================================================

# 봇 인스턴스 생성
bot_instance = ClinicalChatbot()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    서버가 켜질 때(Startup): MCP 연결을 맺고 세션을 시작합니다.
    서버가 꺼질 때(Shutdown): MCP 연결을 안전하게 끊습니다.
    """
    print("🚀 API Server Starting... Connecting to MCP...")
    
    # 봇의 세션을 시작하고, 서버가 실행되는 동안 연결을 유지합니다.
    async with bot_instance.start_session():
        yield # 여기서 서버가 계속 실행됨
        
    print("🛑 API Server Shutting down... Disconnecting MCP...")

# =============================================================================
# 2. FastAPI 앱 설정
# =============================================================================

app = FastAPI(
    title="Clinical AI Chatbot API",
    description="MCP 기반 의료 챗봇 API",
    version="1.0.0",
    lifespan=lifespan # 위에서 정의한 수명 주기 관리자 등록
)

# =============================================================================
# 3. 데이터 모델 정의 (Request/Response)
# =============================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_user"

class ChatResponse(BaseModel):
    reply: str
    session_id: str

# =============================================================================
# 4. API 엔드포인트
# =============================================================================

@app.get("/")
async def root():
    return {"status": "ok", "message": "Clinical Chatbot is running"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    사용자의 메시지를 받아 챗봇의 응답을 반환합니다.
    """
    try:
        # 봇에게 질문 전달 (비동기)
        response_text = await bot_instance.chat(
            user_input=request.message, 
            thread_id=request.session_id
        )
        
        return ChatResponse(
            reply=response_text,
            session_id=request.session_id
        )
    
    except Exception as e:
        # 에러 발생 시 500 에러 반환
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# 5. 실행 (직접 실행 시)
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    # uvicorn server:app --reload 와 동일
    uvicorn.run("api_for_agent:app", host="0.0.0.0", port=8053, reload=True)