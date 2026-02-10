import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Literal, List, Dict, Any, Optional
from typing_extensions import TypedDict

# LangChain / LangGraph Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, ToolMessage, BaseMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# MCP Imports
from mcp.types import CallToolResult
from langchain_mcp_adapters.client import MultiServerMCPClient

from dotenv import load_dotenv
# 1. Load Environment Variables
load_dotenv()

# =============================================================================
# 1. State & Helper Definitions
# =============================================================================

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

def mcp_tools_to_schema(mcp_list_tools_result) -> List[Dict[str, Any]]:
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
# 2. Main Chatbot Class
# =============================================================================

class ClinicalChatbot:
    def __init__(self):
        # Configuration Loading
        self.api_key = os.getenv("GOOGLE_API_KEY", "")
        self.model_name = os.getenv("GOOGLE_MODEL_NAME", "gemini-2.5-flash")
        self.mcp_name = os.getenv("MCP_NAME", "fhir-mcp")
        self.transport = os.getenv("MCP_TRANSPORT_METHOD", "sse")
        self.ip = os.getenv("MCP_IP", "0.0.0.0")
        self.port = int(os.getenv("MCP_PORT", "8052"))
        
        # Internal State
        self.app = None  # Compiled LangGraph App
        self.checkpointer = MemorySaver() # Persistence
        self.client_config = self._build_client_config()

    def _build_client_config(self) -> Dict[str, Any]:
        """MCP Client 연결 설정 생성"""
        if self.transport != 'stdio':
            connection_url = f"http://{self.ip}:{self.port}/{self.transport}"
            return {
                str(self.mcp_name): {
                    "url": str(connection_url),
                    "transport": str(self.transport),
                }
            }
        else:
            # stdio 모드: 현재 실행 파일 기준 경로 설정
            # 주의: __file__이 없는 인터랙티브 환경 고려
            base_dir = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
            server_script = os.path.join(base_dir, "fastmcp_server.py")
            return {
                str(self.mcp_name): {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [server_script],
                }
            }

    @asynccontextmanager
    async def start_session(self):
        """
        [Context Manager] MCP 서버와 연결하고 LangGraph를 초기화합니다.
        사용법:
            async with chatbot.start_session():
                response = await chatbot.chat("안녕")
        """
        client = MultiServerMCPClient(self.client_config)
        print(f"🔌 Connecting to MCP Server ({self.transport})...")

        # Start MCP Session
        async with client.session(self.mcp_name) as mcp:
            try:
                # 1. Load Tools
                mcp_tools = await mcp.list_tools()
                formatted_tools = mcp_tools_to_schema(mcp_tools)
                print(f"🛠️  Loaded {len(formatted_tools)} tools.")

                # 2. Setup LLM
                llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    temperature=0,
                    google_api_key=self.api_key
                )
                llm_with_tools = llm.bind_tools(formatted_tools)

                # 3. Define Graph Nodes (Closure to access 'mcp' session)
                def chatbot_node(state: AgentState):
                    return {"messages": [llm_with_tools.invoke(state["messages"])]}

                async def tool_node(state: AgentState):
                    last_message = state["messages"][-1]
                    tool_results = []
                    for tool_call in last_message.tool_calls:
                        print(f"⚙️  [Tool] {tool_call['name']} args: {tool_call['args']}")
                        try:
                            result: CallToolResult = await mcp.call_tool(
                                name=tool_call["name"],
                                arguments=tool_call["args"]
                            )
                            content = result.content[0].text if result.content else "No content"
                        except Exception as e:
                            content = f"Error: {str(e)}"
                            print(f"❌ Tool Error: {content}")

                        tool_results.append(ToolMessage(
                            tool_call_id=tool_call["id"],
                            name=tool_call["name"],
                            content=str(content)
                        ))
                    return {"messages": tool_results}

                def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
                    if state["messages"][-1].tool_calls:
                        return "tools"
                    return "__end__"

                # 4. Build Graph
                workflow = StateGraph(AgentState)
                workflow.add_node("agent", chatbot_node)
                workflow.add_node("tools", tool_node)
                workflow.add_edge(START, "agent")
                workflow.add_conditional_edges("agent", should_continue)
                workflow.add_edge("tools", "agent")

                self.app = workflow.compile(checkpointer=self.checkpointer)
                
                # Yield control back to the caller
                yield self

            except Exception as e:
                print(f"❌ Session Error: {e}")
                raise
            finally:
                self.app = None
                print("🔌 MCP Session Closed.")

    async def chat(self, user_input: str, thread_id: str = "default_session") -> str:
        """
        [Public API] 사용자의 자연어 입력을 받아 봇의 자연어 응답을 반환합니다.
        
        Args:
            user_input (str): 사용자 질문
            thread_id (str): 대화 컨텍스트 유지를 위한 세션 ID
            
        Returns:
            str: 봇의 최종 응답
        """
        if self.app is None:
            return "❌ Error: Session not started. Use 'async with bot.start_session():'"

        config = {"configurable": {"thread_id": thread_id}}
        final_response = ""

        try:
            # Stream events to process output
            async for event in self.app.astream(
                {"messages": [HumanMessage(content=user_input)]},
                config=config
            ):
                # We only care about the final response from the agent node
                if "agent" in event:
                    msg = event["agent"]["messages"][-1]
                    if msg.content:
                        final_response = self._parse_content(msg.content)
        
        except Exception as e:
            return f"Error during processing: {str(e)}"

        return final_response

    def _parse_content(self, content: Any) -> str:
        """LangChain 메시지 content를 순수 문자열로 변환하는 헬퍼"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # 텍스트 파트만 결합
            return "".join([part.get("text", "") for part in content if isinstance(part, dict)])
        elif isinstance(content, dict):
            return content.get("text", str(content))
        return str(content)

# =============================================================================
# 3. Execution Example
# =============================================================================

async def main():
    # 1. 봇 인스턴스 생성
    bot = ClinicalChatbot()

    # 2. 세션 시작 (연결 수립)
    async with bot.start_session():
        print("\n🤖 Bot is ready. Type 'exit' to quit.")
        
        # 3. 대화 루프
        while True:
            user_in = input("\n👤 User: ")
            if user_in.lower() in ["exit", "quit"]:
                break
            
            # ★ 핵심: 문자열 입력 -> 문자열 출력 함수 사용
            response = await bot.chat(user_in, thread_id="user_123")
            
            print(f"🤖 AI: {response}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())