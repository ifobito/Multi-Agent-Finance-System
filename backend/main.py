import os
import json
import asyncio
import concurrent.futures
from dotenv import load_dotenv
from typing import Dict, List, Any, Callable, TypedDict, Annotated, Literal
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages

# Import các module từ dự án
from src.router.router import FinancialMultiAgentRouter
from src.agent.conversation import ConversationAgent
from src.agent.database_query import DatabaseQueryAgent
from src.agent.google_search import GoogleSearchAgent
from src.agent.visualize_agent import VisualizeAgent

# Load environment variables
load_dotenv()

# Các kiểu dữ liệu
class AgentResult(TypedDict):
    """
    Định nghĩa kiểu dữ liệu cho kết quả của agent.
    
    Attributes:
        agent_name (str): Tên của agent
        content (str): Nội dung kết quả
        additional_data (Dict): Dữ liệu bổ sung (nếu có)
    """
    agent_name: str
    content: str
    additional_data: Dict[str, Any]

class AgentState(TypedDict):
    """
    Định nghĩa kiểu dữ liệu cho trạng thái của luồng xử lý.
    
    Attributes:
        question (str): Câu hỏi từ người dùng
        selected_agents (List[str]): Danh sách các agent được chọn
        agent_results (List[AgentResult]): Kết quả từ các agent
        final_answer (str): Câu trả lời cuối cùng
        status (str): Trạng thái hiện tại
    """
    question: str
    selected_agents: List[str]
    agent_results: List[AgentResult]
    final_answer: str
    status: Literal["ROUTING", "PROCESSING", "COMPLETE"]

class FinancialAgentSystem:
    """
    Hệ thống agent tài chính sử dụng LangGraph để xử lý câu hỏi.
    """
    
    def __init__(self, model_name="gpt-4o-mini"):
        """
        Khởi tạo hệ thống agent tài chính.
        
        Args:
            model_name (str): Tên của mô hình LLM
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = model_name
        self.llm = ChatOpenAI(
            model_name=self.model_name,
            openai_api_key=self.api_key
        )
        
        # Khởi tạo router và các agent
        self.router = FinancialMultiAgentRouter()
        
        # Lấy thông tin kết nối cơ sở dữ liệu từ biến môi trường
        db_host = os.getenv("POSTGRES_HOST", "localhost")
        db_port = os.getenv("POSTGRES_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", "postgres")
        db_user = os.getenv("POSTGRES_USER", "postgres")
        db_password = os.getenv("POSTGRES_PASSWORD", "postgres")
        
        self.agents = {
            "conversation": ConversationAgent(model_name=model_name),
            "database_query": DatabaseQueryAgent(
                host=db_host, 
                port=db_port, 
                dbname=db_name, 
                user=db_user, 
                password=db_password, 
                model_name=model_name
            ),
            "google_search": GoogleSearchAgent(
                api_key=os.getenv("TAVILY_API_KEY"),
                max_retries=3,
                max_results=5
            ),
            "visualize": VisualizeAgent(
                host=db_host, 
                port=db_port, 
                dbname=db_name, 
                user=db_user, 
                password=db_password, 
                model_name=model_name
            )
        }
        
        # Xây dựng đồ thị LangGraph
        self.workflow = self._build_graph()
    
    def _route_question(self, state: AgentState) -> AgentState:
        """
        Định tuyến câu hỏi đến các agent thích hợp.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            AgentState: Trạng thái đã cập nhật
        """
        question = state["question"]
        routing_info = self.router.detailed_routing(question)
        
        print(f"Thông tin định tuyến: {json.dumps(routing_info, indent=2, ensure_ascii=False)}")
        
        state["selected_agents"] = routing_info["selected_agents"]
        state["status"] = "PROCESSING"
        return state
    
    def _run_conversation_agent(self, state: AgentState) -> AgentState:
        """
        Chạy agent conversation và cập nhật kết quả.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            AgentState: Trạng thái đã cập nhật
        """
        if "conversation" not in state["selected_agents"]:
            return state
        
        try:
            result = self.agents["conversation"].process_message(state["question"])
            agent_result = {
                "agent_name": "conversation",
                "content": result["message"],
                "additional_data": {"type": result["type"]}
            }
            state["agent_results"].append(agent_result)
        except Exception as e:
            print(f"Lỗi khi chạy agent conversation: {str(e)}")
        
        return state
    
    def _run_database_query_agent(self, state: AgentState) -> AgentState:
        """
        Chạy agent database_query và cập nhật kết quả.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            AgentState: Trạng thái đã cập nhật
        """
        if "database_query" not in state["selected_agents"]:
            return state
        
        try:
            result = self.agents["database_query"].query_with_retry(state["question"])
            
            # Tạo nội dung định dạng từ kết quả
            formatted_content = ""
            if result and "results" in result and result["results"]:
                formatted_content = "Kết quả truy vấn cơ sở dữ liệu:\n"
                formatted_content += f"SQL: {result.get('query', '')}\n\n"
                
                # Thêm header của các cột
                if "columns" in result and result["columns"]:
                    formatted_content += "| " + " | ".join(result["columns"]) + " |\n"
                    formatted_content += "| " + " | ".join(["-" * len(col) for col in result["columns"]]) + " |\n"
                
                # Thêm dữ liệu hàng
                for row in result["results"]:
                    if isinstance(row, dict):
                        formatted_content += "| " + " | ".join([str(row.get(col, "")) for col in result["columns"]]) + " |\n"
            else:
                formatted_content = "Không tìm thấy dữ liệu phù hợp."
            
            agent_result = {
                "agent_name": "database_query",
                "content": formatted_content,
                "additional_data": {
                    "success": True if result and "results" in result else False,
                    "query": result.get("query", ""),
                    "columns": result.get("columns", []),
                    "results": result.get("results", [])
                }
            }
            state["agent_results"].append(agent_result)
        except Exception as e:
            print(f"Lỗi khi chạy agent database_query: {str(e)}")
        
        return state
    
    def _run_google_search_agent(self, state: AgentState) -> AgentState:
        """
        Chạy agent google_search và cập nhật kết quả.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            AgentState: Trạng thái đã cập nhật
        """
        if "google_search" not in state["selected_agents"]:
            return state
        
        try:
            result = self.agents["google_search"].search_with_retry(state["question"])
            
            # Tạo nội dung định dạng từ kết quả
            formatted_content = ""
            if result and result["status"] == "success" and "results" in result:
                formatted_content = "Kết quả tìm kiếm từ Google:\n\n"
                
                for i, item in enumerate(result["results"], 1):
                    formatted_content += f"{i}. **{item.get('title', 'Không có tiêu đề')}**\n"
                    formatted_content += f"   URL: {item.get('url', 'Không có URL')}\n"
                    formatted_content += f"   {item.get('content', 'Không có nội dung')}\n\n"
            else:
                formatted_content = result.get("message", "Không tìm thấy kết quả phù hợp.")
            
            agent_result = {
                "agent_name": "google_search",
                "content": formatted_content,
                "additional_data": {
                    "success": result["status"] == "success" if "status" in result else False,
                    "search_results": result.get("results", [])
                }
            }
            state["agent_results"].append(agent_result)
        except Exception as e:
            print(f"Lỗi khi chạy agent google_search: {str(e)}")
        
        return state
    
    def _run_visualize_agent(self, state: AgentState) -> AgentState:
        """
        Chạy agent visualize và cập nhật kết quả.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            AgentState: Trạng thái đã cập nhật
        """
        if "visualize" not in state["selected_agents"]:
            return state
        
        try:
            result = self.agents["visualize"].visualize_query_result(state["question"])
            content = f"Biểu đồ đã được tạo và lưu tại: {result['visualization_path']}" if result["success"] else result["message"]
            
            agent_result = {
                "agent_name": "visualize",
                "content": content,
                "additional_data": {
                    "success": result["success"],
                    "chart_info": result.get("chart_info", {}),
                    "visualization_path": result.get("visualization_path", ""),
                    "visualization_base64": result.get("visualization_base64", "")
                }
            }
            state["agent_results"].append(agent_result)
        except Exception as e:
            print(f"Lỗi khi chạy agent visualize: {str(e)}")
        
        return state
    
    def _synthesize_results(self, state: AgentState) -> AgentState:
        """
        Tổng hợp kết quả từ các agent để tạo câu trả lời cuối cùng.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            AgentState: Trạng thái đã cập nhật
        """
        if not state["agent_results"]:
            state["final_answer"] = "Không có kết quả từ bất kỳ agent nào. Vui lòng thử lại với câu hỏi khác."
            state["status"] = "COMPLETE"
            return state
        
        # Tạo context từ kết quả của các agent
        context = ""
        for result in state["agent_results"]:
            context += f"\n--- Kết quả từ {result['agent_name']} ---\n"
            context += result["content"] + "\n"
            
            # Thêm thông tin về biểu đồ nếu có
            if result["agent_name"] == "visualize" and result["additional_data"]["success"]:
                chart_info = result["additional_data"]["chart_info"]
                context += f"\nThông tin biểu đồ: {json.dumps(chart_info, ensure_ascii=False)}\n"
        
        # Lấy danh sách các agent đã được sử dụng
        used_agents = []
        for result in state["agent_results"]:
            if result["agent_name"] not in used_agents:
                used_agents.append(result["agent_name"])
        
        # Sử dụng LLM để tổng hợp kết quả
        prompt = f"""
        Dựa trên kết quả từ các agent khác nhau, hãy tạo một câu trả lời tổng hợp, logic và dễ hiểu cho câu hỏi sau của người dùng.
        
        Câu hỏi: {state["question"]}
        
        Kết quả từ các agent:
        {context}
        
        Hãy tổng hợp thông tin trên để trả lời câu hỏi một cách đầy đủ, chính xác, và dễ hiểu.
        Nếu có biểu đồ, hãy đề cập đến nó và giải thích ý nghĩa của biểu đồ.
        Nếu có dữ liệu số liệu cụ thể, hãy trích dẫn chúng.
        Nếu có thông tin mới nhất từ tìm kiếm Google, hãy đề cập đến nguồn.
        """
        
        response = self.llm.invoke(prompt)
        
        # Thêm thông tin về các agent đã sử dụng vào câu trả lời cuối cùng
        agent_info = "\n\n---\n*Các agent được sử dụng: " + ", ".join(used_agents) + "*"
        
        state["final_answer"] = response.content + agent_info
        state["status"] = "COMPLETE"
        return state
    
    def _should_route(self, state: AgentState) -> Literal["route"]:
        """
        Kiểm tra xem có cần định tuyến câu hỏi không.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            Literal["route"]: Luôn trả về "route" nếu đang ở trạng thái ROUTING
        """
        if state["status"] == "ROUTING":
            return "route"
        else:
            raise ValueError(f"Invalid state for routing: {state['status']}")
    
    def _should_end(self, state: AgentState) -> Literal["end", "process"]:
        """
        Kiểm tra xem luồng xử lý có nên kết thúc hay không.
        
        Args:
            state (AgentState): Trạng thái hiện tại
            
        Returns:
            Literal["end", "process"]: "end" nếu hoàn thành, "process" nếu cần tiếp tục
        """
        if state["status"] == "COMPLETE":
            return "end"
        elif state["status"] == "PROCESSING":
            return "process"
        else:
            raise ValueError(f"Invalid state for checking end: {state['status']}")
    
    def _build_graph(self) -> StateGraph:
        """
        Xây dựng đồ thị luồng xử lý LangGraph.
        
        Returns:
            StateGraph: Đồ thị đã khởi tạo
        """
        # Khởi tạo đồ thị
        workflow = StateGraph(AgentState)
        
        # Thêm các node
        workflow.add_node("router", self._route_question)
        workflow.add_node("conversation_agent", self._run_conversation_agent)
        workflow.add_node("database_query_agent", self._run_database_query_agent)
        workflow.add_node("google_search_agent", self._run_google_search_agent)
        workflow.add_node("visualize_agent", self._run_visualize_agent)
        workflow.add_node("synthesizer", self._synthesize_results)
        
        # Thiết lập node bắt đầu là router
        workflow.set_entry_point("router")
        
        # Thêm các edge giữa các node
        workflow.add_edge("router", "conversation_agent")
        workflow.add_edge("conversation_agent", "database_query_agent")
        workflow.add_edge("database_query_agent", "google_search_agent")
        workflow.add_edge("google_search_agent", "visualize_agent")
        workflow.add_edge("visualize_agent", "synthesizer")
        
        workflow.add_conditional_edges(
            "synthesizer",
            self._should_end,
            {
                "end": END,
                "process": "conversation_agent"  # Loop back if needed
            }
        )
        
        # Compile đồ thị
        return workflow.compile()
    
    async def process_question_async(self, question: str, selected_agent: str = None) -> str:
        """
        Xử lý câu hỏi của người dùng thông qua luồng đồ thị LangGraph bằng cách bất đồng bộ.
        
        Args:
            question (str): Câu hỏi từ người dùng
            selected_agent (str, optional): Tên agent cụ thể muốn sử dụng. Nếu None, hệ thống sẽ tự động định tuyến.
            
        Returns:
            str: Câu trả lời cuối cùng
        """
        # Hàm chạy các tác vụ đồng bộ trong thread pool để không chặn event loop
        async def run_in_threadpool(func, *args, **kwargs):
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return await loop.run_in_executor(
                    pool, lambda: func(*args, **kwargs)
                )
        
        # Khởi tạo trạng thái ban đầu
        initial_state: AgentState = {
            "question": question,
            "selected_agents": [selected_agent] if selected_agent else [],
            "agent_results": [],
            "final_answer": "",
            "status": "PROCESSING" if selected_agent else "ROUTING"
        }
        
        if selected_agent:
            print(f"Chạy agent {selected_agent} theo yêu cầu thủ công (bất đồng bộ)")
        
        # Chạy luồng xử lý trong thread riêng để không chặn event loop
        final_state = await run_in_threadpool(self.workflow.invoke, initial_state)
        
        # Trả về kết quả cuối cùng
        return final_state["final_answer"]
        
    def process_question(self, question: str, selected_agent: str = None) -> str:
        """
        Xử lý câu hỏi của người dùng thông qua luồng đồ thị LangGraph.
        
        Args:
            question (str): Câu hỏi từ người dùng
            selected_agent (str, optional): Tên agent cụ thể muốn sử dụng. Nếu None, hệ thống sẽ tự động định tuyến.
            
        Returns:
            str: Câu trả lời cuối cùng
        """
        # Khởi tạo trạng thái ban đầu
        initial_state: AgentState = {
            "question": question,
            "selected_agents": [selected_agent] if selected_agent else [],
            "agent_results": [],
            "final_answer": "",
            "status": "PROCESSING" if selected_agent else "ROUTING"
        }
        
        if selected_agent:
            print(f"Chạy agent {selected_agent} theo yêu cầu thủ công")
        
        # Chạy luồng xử lý
        final_state = self.workflow.invoke(initial_state)
        
        # Trả về kết quả cuối cùng
        return final_state["final_answer"]

def main(test_mode=True):
    """
    Hàm chính để chạy hệ thống agent tài chính.
    
    Args:
        test_mode (bool): Nếu True, sẽ chạy với câu hỏi mẫu. Nếu False, sẽ chạy trong chế độ tương tác với người dùng.
    """
    agent_system = FinancialAgentSystem()
    
    # Danh sách các agent có sẵn
    available_agents = [
        "auto",  # Tự động định tuyến
        "conversation",
        "database_query",
        "google_search",
        "visualize"
    ]
    
    print("Hệ thống Agent Tài chính")
    
    if test_mode:
        # Các câu hỏi mẫu để kiểm tra hệ thống
        test_questions = [
            "Plot the time series of Microsoft (MSFT) stock closing price from June 1, 2024 to September 30, 2024."
        ]
        
        # Chọn câu hỏi đầu tiên để kiểm tra
        question = test_questions[0]
        print(f"\nCâu hỏi kiểm tra: {question}")
        print("\nĐang xử lý...")
        try:
            answer = agent_system.process_question(question)
            print(f"\nTrả lời: {answer}")
        except Exception as e:
            print(f"\nLỗi: {str(e)}")
    else:
        # Chế độ tương tác
        print("Nhập 'exit' để thoát.")
        print("Nhập 'agent' để xem và chọn agent cụ thể.")
        
        # Mặc định sử dụng định tuyến tự động
        current_agent = None
        
        while True:
            try:
                question = input("\nCâu hỏi của bạn" + (f" [{current_agent}]" if current_agent else "") + ": ")
                
                if question.lower() == "exit":
                    break
                    
                elif question.lower() == "agent":
                    print("\nCác agent có sẵn:")
                    for i, agent in enumerate(available_agents):
                        print(f"{i}. {agent}" + (" (mặc định)" if agent == "auto" and current_agent is None else ""))
                    
                    choice = input("Chọn agent (nhập số hoặc tên agent): ")
                    
                    # Xử lý lựa chọn agent
                    try:
                        if choice.isdigit() and 0 <= int(choice) < len(available_agents):
                            agent_choice = available_agents[int(choice)]
                        elif choice in available_agents:
                            agent_choice = choice
                        else:
                            print("Lựa chọn không hợp lệ. Sử dụng chế độ tự động.")
                            agent_choice = "auto"
                            
                        current_agent = None if agent_choice == "auto" else agent_choice
                        print(f"\nĐã chọn: {agent_choice}" + (" (tự động định tuyến)" if agent_choice == "auto" else ""))
                    except Exception as e:
                        print(f"Lỗi khi chọn agent: {str(e)}")
                        current_agent = None
                
                else:
                    print("\nĐang xử lý...")
                    try:
                        # Sử dụng agent đã chọn hoặc tự động định tuyến
                        import asyncio
                        loop = asyncio.get_event_loop()
                        result = loop.run_until_complete(agent_system.process_question_async(question, current_agent))
                        print(f"\nTrả lời: {result}")
                        print(f"\nTrả lời: {answer}")
                    except Exception as e:
                        print(f"\nLỗi: {str(e)}")
                        print("Thử chọn agent khác bằng cách nhập 'agent'.")
            except EOFError:
                # Xử lý trường hợp kết thúc đầu vào
                print("\nKết thúc chương trình do kết thúc đầu vào.")
                break

if __name__ == "__main__":
    main()
