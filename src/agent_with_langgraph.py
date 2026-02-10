import asyncio
import os
import sys
from typing import Annotated, Literal, List
from typing_extensions import TypedDict

# LangChain / LangGraph Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, ToolMessage, BaseMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver # 대화 기억용

# MCP Imports (User's custom client & Standard types)
from mcp.types import CallToolResult
# from your_module import MultiServerMCPClient  <-- 사용자의 클래스 import 필요

from dotenv import load_dotenv
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL_NAME = os.getenv("GOOGLE_MODEL_NAME", "gemini-2.5-flash")
MCP_TRANSPORT_METHOD = os.getenv("MCP_TRANSPORT_METHOD", "sse")  # 'sse' or 'stdio'

MCP_NAME = os.getenv("MCP_NAME", "fhir-mcp")
MCP_IP = os.getenv("MCP_IP", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8052"))
mcp_set_dict = {}
if MCP_TRANSPORT_METHOD != 'stdio':
    mcp_connection = f"http://{MCP_IP}:{MCP_PORT}/{MCP_TRANSPORT_METHOD}"

    mcp_set_dict = {
            str(MCP_NAME): {
                "url": str(mcp_connection),
                "transport": str(MCP_TRANSPORT_METHOD),
            }
        }
else:
    # stdio 모드인 경우, 별도 설정 없이 subprocess에서 자동 연결됨
    mcp_set_dict = {
            str(MCP_NAME): {
                "transport": "stdio",
                "command": sys.executable,
                "args": [os.path.join(os.path.dirname(__file__), "fastmcp_server.py")],
            }
        }
# =============================================================================
# 1. Helper Functions & State Definition
# =============================================================================

class AgentState(TypedDict):
    # add_messages: 이전 대화 내용을 계속 리스트에 누적(Append)하는 Reducer
    messages: Annotated[List[BaseMessage], add_messages]

def mcp_tools_to_schema(mcp_list_tools_result):
    """MCP Tool 정의를 Gemini가 이해하는 JSON Schema로 변환"""
    tools_schema = []
    for tool in mcp_list_tools_result.tools:
        tools_schema.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema
        })
    return tools_schema

# =============================================================================
# 2. Main Chat Application
# =============================================================================

async def run_chat_app():
    # 1. MCP Client 설정 (사용자 제공 코드)
    # 실제로는 MultiServerMCPClient 클래스가 정의되어 있어야 합니다.
    # 여기서는 import 했다고 가정하거나, 기존 코드를 그대로 사용합니다.
    from langchain_mcp_adapters.client import MultiServerMCPClient # (예시) 파일 분리 권장

    client = MultiServerMCPClient(mcp_set_dict)
    print("🔌 Connecting to MCP Server...")

    # ★ 핵심: 세션 컨텍스트 안에서 챗봇 루프를 실행해야 함 ★
    async with client.session(MCP_NAME) as mcp:
        
        # 2. 도구 로드 및 LLM 설정
        try:
            mcp_tools = await mcp.list_tools()
            formatted_tools = mcp_tools_to_schema(mcp_tools)
            print(f"🛠️  Loaded {len(formatted_tools)} tools from MCP Server.")
        except Exception as e:
            print(f"❌ Error loading tools: {e}")
            return

        # Gemini 모델 초기화
        llm = ChatGoogleGenerativeAI(
            model=GOOGLE_MODEL_NAME,
            temperature=0,
            google_api_key=GOOGLE_API_KEY
        )
        llm_with_tools = llm.bind_tools(formatted_tools)

        # ---------------------------------------------------------------------
        # 3. Graph Nodes Definition (내부 함수로 정의하여 'mcp' 변수 접근)
        # ---------------------------------------------------------------------
        
        # [Node 1] 챗봇(Agent) 노드
        def chatbot_node(state: AgentState):
            return {"messages": [llm_with_tools.invoke(state["messages"])]}

        # [Node 2] 도구 실행(Tool) 노드
        async def tool_node(state: AgentState):
            last_message = state["messages"][-1]
            tool_results = []

            for tool_call in last_message.tool_calls:
                print(f"\n⚙️  [Tool Call] {tool_call['name']} (Args: {tool_call['args']})")
                
                try:
                    # MCP 세션을 사용하여 실제 도구 호출
                    result: CallToolResult = await mcp.call_tool(
                        name=tool_call["name"],
                        arguments=tool_call["args"]
                    )
                    
                    # 결과 텍스트 추출
                    content = result.content[0].text if result.content else "No content returned."
                    print(f"   ✅ Result: {content[:100]}..." if len(content) > 100 else f"   ✅ Result: {content}")

                except Exception as e:
                    content = f"Error executing tool: {str(e)}"
                    print(f"   ❌ Error: {content}")

                # 결과 메시지 생성
                tool_results.append(ToolMessage(
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    content=str(content)
                ))
            
            return {"messages": tool_results}

        # [Edge] 조건부 분기
        def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
            last_message = state["messages"][-1]
            if last_message.tool_calls:
                return "tools"
            return "__end__"

        # ---------------------------------------------------------------------
        # 4. Graph Construction
        # ---------------------------------------------------------------------
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", chatbot_node)
        workflow.add_node("tools", tool_node)

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")

        # MemorySaver: 대화 내역을 메모리에 저장 (Multi-turn 핵심)
        checkpointer = MemorySaver()
        app = workflow.compile(checkpointer=checkpointer)

        # ---------------------------------------------------------------------
        # 5. Interactive Chat Loop (Multi-turn)
        # ---------------------------------------------------------------------
        thread_id = "session-1" # 사용자 세션 ID
        config = {"configurable": {"thread_id": thread_id}}
        
        print("\n" + "="*50)
        print("🤖 Clinical AI Chatbot is Ready! (type 'exit' to quit)")
        print("="*50)

        while True:
            try:
                user_input = input("\n👤 User: ")
                if user_input.lower() in ["exit", "quit", "그만"]:
                    print("👋 Chat session ended.")
                    break
                
                # 그래프 실행 (스트리밍 모드)
                # 이전 대화 기록은 checkpointer가 관리하므로 새로운 입력만 넣으면 됨
                async for event in app.astream(
                    {"messages": [HumanMessage(content=user_input)]}, 
                    config=config
                ):
                    for key, value in event.items():
                        if key == "agent":
                            msg = value["messages"][-1]
                            if msg.content:
                                content = msg.content
                                if isinstance(content, list):
                                    text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
                                    print(f"🤖 AI: {''.join(text_parts) if text_parts else content}")
                                elif isinstance(content, dict):
                                    print(f"🤖 AI: {content.get('text', content)}")
                                else:
                                    print(f"🤖 AI: {content}")
                        # tool 출력은 위 node에서 print 찍음
            
            except KeyboardInterrupt:
                print("\n👋 Forced exit.")
                break
            except Exception as e:
                print(f"❌ System Error: {e}")

if __name__ == "__main__":
    # Windows 환경 asyncio 정책 설정 (필요시)
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(run_chat_app())
    