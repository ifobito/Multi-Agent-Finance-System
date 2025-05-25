import os
import json
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from dataclasses import dataclass
from typing import List, Dict, Any
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Agent:
    name: str
    description: str
    threshold: float  # Ngưỡng confidence để chọn agent
    confidence: float = 0.0
    selected: bool = False

class FinancialMultiAgentRouter:
    def __init__(self):
        """
        Khởi tạo bộ định tuyến đa tác nhân cho các câu hỏi tài chính.
        Không bao gồm vector_search và chỉ dùng visualize khi confidence > 0.9
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=self.api_key
        )
            
        self.agents = [
            Agent(
                name="database_query",
                description="Xử lý truy vấn cơ sở dữ liệu về thông tin công ty và giá cổ phiếu.",
                threshold=0.2
            ),
            Agent(
                name="google_search",
                description="Tìm kiếm trên Google để lấy thông tin mới nhất về công ty và giá cổ phiếu.",
                threshold=0.2
            ),
            Agent(
                name="visualize",
                description="Tạo truy vấn và trực quan hóa dữ liệu dưới dạng biểu đồ, đồ thị và các hình ảnh trực quan khác.",
                threshold=0.7 
            ),
            Agent(
                name="conversation",
                description="Xử lý các tương tác giao tiếp và lời chào.",
                threshold=0.2
            )
        ]

    def parse_confidence_json(self, raw_output: str) -> Dict[str, float]:
        """
        Phân tích JSON chứa điểm tin cậy từ đầu ra của LLM.
        
        Args:
            raw_output (str): Đầu ra thô từ LLM
        Returns:
            Dict chứa điểm tin cậy cho từng tác nhân
        """
        json_match = re.search(r'\{[^{}]+\}', raw_output)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                logger.warning("Không thể phân tích JSON, thử phương pháp khác")
        
        clean_output = raw_output.replace('```json', '').replace('```', '').strip()
        try:
            return json.loads(clean_output)
        except:
            logger.warning("Sử dụng phương pháp phân tích dự phòng")
            confidence_dict = {agent.name: 0.0 for agent in self.agents}
            for agent in self.agents:
                match = re.search(rf'{agent.name}["\']?\s*:\s*(\d+\.?\d*)', raw_output)
                if match:
                    confidence_dict[agent.name] = float(match.group(1))
            return confidence_dict

    def calculate_confidence(self, question: str) -> List[Agent]:
        """
        Tính toán điểm tin cậy cho mỗi tác nhân dựa trên câu hỏi.
        
        Args:
            question (str): Câu hỏi của người dùng
        Returns:
            Danh sách các tác nhân với điểm tin cậy được cập nhật
        """
        try:
            agents = self._llm_intent_classification(question)
            return agents
        except Exception as e:
            logger.error(f"Phân loại bằng LLM thất bại: {e}")
            return self.agents

    def _llm_intent_classification(self, question: str) -> List[Agent]:
        """
        Sử dụng LLM để phân loại ý định của câu hỏi.
        
        Args:
            question (str): Câu hỏi của người dùng
        Returns:
            Danh sách các tác nhân với điểm tin cậy được cập nhật
        """
        prompt = f"""
        Phân loại câu hỏi sau vào một hoặc nhiều danh mục sau:
        1. database_query - Câu hỏi về thông tin công ty hoặc giá cổ phiếu
        2. google_search - Câu hỏi yêu cầu tin tức mới nhất về công ty hoặc giá cổ phiếu
        3. visualize - Câu hỏi yêu cầu tạo biểu đồ, đồ thị hoặc các hình ảnh trực quan hóa dữ liệu
        4. conversation - Lời chào hoặc giao tiếp thông thường
        
        Câu hỏi: {question}
        
        Hãy xem xét kỹ độ phù hợp của câu hỏi với từng danh mục. Đặc biệt lưu ý:
        - Nếu câu hỏi liên quan đến "biểu đồ", "trực quan hóa", "histogram", "line chart", "boxplot", "pie chart",
          "scatter plot", hoặc các từ liên quan đến việc tạo hình ảnh từ dữ liệu, hãy ưu tiên định tuyến cho "visualize".
        - Visualize cần phải có điểm tin cậy rất cao (trên 0.9) để được sử dụng
        
        Trả về JSON với điểm tin cậy cho mỗi danh mục, tổng bằng 1.0.
        Ví dụ: {{"database_query": 0.2, "google_search": 0.1, "visualize": 0.6, "conversation": 0.1}}
        """
        
        raw_output = self.llm.invoke(prompt)
        confidence_scores = self.parse_confidence_json(raw_output.content)
        
        for agent in self.agents:
            agent.confidence = confidence_scores.get(agent.name, 0.0)
            agent.selected = agent.confidence >= agent.threshold
        
        return self.agents

    def select_agents(self, question: str) -> List[str]:
        """
        Chọn các tác nhân dựa trên điểm tin cậy và ngưỡng riêng của mỗi agent.
        
        Args:
            question (str): Câu hỏi của người dùng
        Returns:
            Danh sách tên các tác nhân được chọn
        """
        agents = self.calculate_confidence(question)
        selected_agents = [agent.name for agent in agents if agent.selected]
        return selected_agents if selected_agents else ["conversation"]

    def detailed_routing(self, question: str) -> Dict[str, Any]:
        """
        Cung cấp thông tin định tuyến chi tiết.
        
        Args:
            question (str): Câu hỏi của người dùng
        Returns:
            Thông tin định tuyến chi tiết
        """
        agents = self.calculate_confidence(question)
        
        return {
            "question": question,
            "agents": [
                {
                    "name": agent.name,
                    "confidence": round(agent.confidence, 2),
                    "threshold": agent.threshold,
                    "selected": agent.selected
                } for agent in agents
            ],
            "selected_agents": self.select_agents(question)
        }

def main():
    router = FinancialMultiAgentRouter()
    
    test_questions = [
        "Xin chào, bạn khỏe không?",
        "Giá cổ phiếu của Apple hôm nay là bao nhiêu?",
        "Tiì kiếm trên Google về tin tức của Apple?",
        "Tin tức mới nhất về AI của Google là gì?",
        "Cho tôi báo cáo tài chính và giá cổ phiếu hiện tại của Microsoft",
        "Create a pie chart of market capitalization proportions by sector as of 2024."
    ]
    
    for question in test_questions:
        print(f"\nCâu hỏi: {question}")
        routing_info = router.detailed_routing(question)
        
        print("Điểm tin cậy của các tác nhân:")
        for agent in routing_info['agents']:
            print(f"{agent['name'].replace('_', ' ').title()}: "
                  f"{agent['confidence']:.2f}/{agent['threshold']:.2f} {'(Được chọn)' if agent['selected'] else ''}")
        
        print(f"Các tác nhân được chọn: {routing_info['selected_agents']}")

if __name__ == "__main__":
    main()