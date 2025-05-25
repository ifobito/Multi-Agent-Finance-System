import os
import json
import base64
import asyncio
import concurrent.futures
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import warnings

# Tắt cảnh báo từ LangChain
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*LLMChain was deprecated.*")

# Import lớp FinancialAgentSystem từ main.py
from main import FinancialAgentSystem

# Thiết lập logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load biến môi trường
load_dotenv()

app = FastAPI(title="Financial Multi-Agent API")

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả các nguồn gốc trong môi trường phát triển
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo hệ thống agent tài chính
agent_system = FinancialAgentSystem()

# Tạo thư mục lưu biểu đồ nếu chưa tồn tại
if not os.path.exists("./visualizations"):
    os.makedirs("./visualizations")
    logger.info("Đã tạo thư mục lưu biểu đồ")

# Mount thư mục visualizations để phục vụ tệp tĩnh
app.mount("/visualizations", StaticFiles(directory="visualizations"), name="visualizations")
logger.info("Đã mount thư mục visualizations để phục vụ tệp tĩnh")

# Định nghĩa models
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    routing_info: Dict[str, Any]
    visualization_base64: Optional[str] = None
    current_agent: Optional[str] = "conversation"  # Thêm trường current_agent với giá trị mặc định
    
# Tạo một đối tượng ThreadPoolExecutor để chạy các tác vụ không phải async trong thread riêng
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

async def run_in_threadpool(func, *args, **kwargs):
    """
    Chạy một hàm đồng bộ trong thread pool để không chặn event loop.
    
    Args:
        func: Hàm cần chạy
        args, kwargs: Các tham số cho hàm
    Returns:
        Kết quả của hàm
    """
    return await asyncio.get_event_loop().run_in_executor(
        executor, lambda: func(*args, **kwargs)
    )

async def process_question_async(question: str) -> Dict[str, Any]:
    """
    Xử lý câu hỏi của người dùng thông qua FinancialAgentSystem.
    
    Args:
        question (str): Câu hỏi của người dùng
    Returns:
        Dict: Kết quả xử lý từ hệ thống agent tài chính
    """
    try:
        # Lấy thông tin định tuyến từ router (chạy trong thread riêng)
        routing_info = await run_in_threadpool(agent_system.router.detailed_routing, question)
        logger.info(f"Thông tin định tuyến: {json.dumps(routing_info, ensure_ascii=False, indent=2)}")
        
        # Xử lý câu hỏi thông qua hệ thống agent (chạy trong thread riêng)
        final_answer = await run_in_threadpool(agent_system.process_question, question)
        logger.info(f"Xử lý câu hỏi hoàn tất")
        
        # Tìm kiếm thông tin biểu đồ (nếu có)
        visualization_base64 = None
        if "visualize" in routing_info["selected_agents"]:
            # Truy cập trực tiếp vào kết quả cuối cùng của workflow
            try:
                # Lấy final_state từ lần chạy cuối cùng của workflow
                # Tạo config mặc định để truyền vào hàm get_state
                config = {"configurable": {"thread_id": "default"}}
                final_state = await run_in_threadpool(agent_system.workflow.get_state, config)
                agent_results = final_state.get('agent_results', [])
                
                for result in agent_results:
                    if result.get("agent_name") == "visualize" and result.get("additional_data", {}).get("success", False):
                        visualization_base64 = result.get("additional_data", {}).get("visualization_base64", None)
                        if visualization_base64:
                            logger.info("Tìm thấy dữ liệu biểu đồ")
                        break
            except Exception as viz_error:
                logger.warning(f"Không thể truy cập kết quả visualize: {viz_error}")
        
        # Thêm thông tin agent hiện tại đang xử lý dựa trên routing_info
        current_agent = "conversation"  # Mặc định là conversation
        
        # Xác định agent hiện tại dựa trên selected_agents và kết quả
        if routing_info and "selected_agents" in routing_info and routing_info["selected_agents"]:
            # Xác định agent cuối cùng dựa trên thứ tự ưu tiên
            if "visualize" in routing_info["selected_agents"] and visualization_base64:
                current_agent = "visualize"
            elif "database_query" in routing_info["selected_agents"]:
                current_agent = "database_query"
            elif "google_search" in routing_info["selected_agents"]:
                current_agent = "google_search"
            else:
                current_agent = routing_info["selected_agents"][0]
        
        # Lấy trạng thái cuối cùng của workflow để kiểm tra agent_results
        try:
            config = {"configurable": {"thread_id": "default"}}
            final_state = await run_in_threadpool(agent_system.workflow.get_state, config)
            
            # Kiểm tra trực tiếp trong agent_results nếu có
            if final_state and "agent_results" in final_state and final_state["agent_results"]:
                # Lấy agent cuối cùng hoạt động trong chuỗi xử lý
                for result in reversed(final_state["agent_results"]):
                    if result.get("agent_name") in ["visualize", "database_query", "google_search", "conversation"]:
                        current_agent = result["agent_name"]
                        break
        except Exception as e:
            logger.warning(f"Không thể lấy thông tin agent_results: {e}")
        
        return {
            "answer": final_answer,
            "routing_info": routing_info,
            "visualization_base64": visualization_base64,
            "current_agent": current_agent
        }
    
    except Exception as e:
        logger.error(f"Lỗi khi xử lý câu hỏi: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(e)}")

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Xử lý câu hỏi từ người dùng và trả về kết quả từ hệ thống agent tài chính.
    """
    question = request.question
    logger.info(f"Nhận câu hỏi: {question}")
    
    result = await process_question_async(question)
    
    # Đảm bảo trả về current_agent cho frontend
    return {
        "answer": result["answer"],
        "routing_info": result["routing_info"],
        "visualization_base64": result["visualization_base64"],
        "current_agent": result.get("current_agent", "conversation")  # Đặt mặc định là conversation nếu không có
    }

@app.get("/api/health")
async def health_check():
    """Kiểm tra trạng thái hoạt động của API."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    
    # Thông tin cấu hình API
    host = "0.0.0.0"
    port = 8000
    
    print(f"\n{'='*50}")
    print(f"Khởi động Financial Multi-Agent API tại http://{host}:{port}")
    print(f"API docs: http://{host}:{port}/docs")
    print(f"Nhấn Ctrl+C để dừng server")
    print(f"{'='*50}\n")
    
    # Khởi động server
    uvicorn.run("api:app", host=host, port=port, reload=True)
