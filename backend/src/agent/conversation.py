import os
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
import time
from datetime import datetime

class ConversationAgent:
    def __init__(self, max_retries=3, model_name="gpt-4o-mini"):
        """Khởi tạo agent xử lý giao tiếp và lời chào."""
        load_dotenv()
        
        # Khởi tạo LLM
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.llm = ChatOpenAI(
            model_name=model_name,
            openai_api_key=self.api_key
        )
        
        # Đặt các tham số
        self.max_retries = max_retries
        
        # Tạo prompt cho cuộc trò chuyện
        self.conversation_prompt = PromptTemplate(
            input_variables=["input", "user_context"],
            template="""
            Bạn là trợ lý thông tin tài chính, hãy phản hồi một cách lịch sự, chuyên nghiệp và đúng trọng tâm.
            
            Thông tin về người dùng (nếu có):
            {user_context}
            
            Tin nhắn của người dùng:
            {input}
            
            Phản hồi của bạn (bằng tiếng Việt, giọng điệu thân thiện nhưng chuyên nghiệp):
            """
        )
        
        # Sử dụng RunnableSequence thay vì LLMChain
        self.chain = self.conversation_prompt | self.llm
        
        # Danh sách lời chào và câu hỏi thông thường
        self.greetings = [
            "xin chào", "chào", "hello", "hi", "hey", "alo", "chào bạn", 
            "chào buổi sáng", "chào buổi chiều", "chào buổi tối"
        ]
        
        self.common_questions = [
            "bạn là ai", "bạn có thể làm gì", "giúp tôi", "trợ giúp", 
            "hướng dẫn", "khả năng", "chức năng"
        ]

    def is_greeting(self, message):
        """Kiểm tra xem tin nhắn có phải là lời chào không."""
        message = message.lower()
        return any(greeting in message for greeting in self.greetings)
    
    def is_help_request(self, message):
        """Kiểm tra xem tin nhắn có phải là yêu cầu trợ giúp không."""
        message = message.lower()
        return any(question in message for question in self.common_questions)
    
    def get_standard_response(self, message):
        """Trả về phản hồi chuẩn cho các trường hợp thông thường."""
        message = message.lower()
        
        if self.is_greeting(message):
            current_hour = datetime.now().hour
            
            if 5 <= current_hour < 12:
                greeting = "Chào buổi sáng"
            elif 12 <= current_hour < 18:
                greeting = "Chào buổi chiều"
            else:
                greeting = "Chào buổi tối"
                
            return {
                "type": "greeting",
                "message": f"{greeting}! Tôi là trợ lý thông tin tài chính. Tôi có thể giúp gì cho bạn về thông tin công ty, giá cổ phiếu, hoặc tin tức tài chính?"
            }
        
        elif self.is_help_request(message):
            return {
                "type": "help",
                "message": """Tôi có thể giúp bạn:
                1. Tìm kiếm thông tin tài chính và tin tức mới nhất về các công ty
                2. Tra cứu giá cổ phiếu và dữ liệu thị trường
                3. Truy vấn cơ sở dữ liệu về thông tin công ty và lịch sử giá cổ phiếu
                4. Trả lời các câu hỏi chung về tài chính và đầu tư

                Bạn có thể hỏi những câu như:
                - "Giá cổ phiếu của Apple hôm nay là bao nhiêu?"
                - "Cho tôi tin tức mới nhất về Tesla"
                - "Thông tin về công ty Microsoft"
                - "Xu hướng thị trường chứng khoán gần đây"
                """
            }
        
        return None

    async def process_message_async(self, message, user_context=None):
        """
        Xử lý tin nhắn của người dùng và trả về phản hồi bằng cách bất đồng bộ.
        
        Args:
            message (str): Tin nhắn của người dùng
            user_context (str, optional): Thông tin ngữ cảnh của người dùng
        Returns:
            Dict chứa loại và nội dung phản hồi
        """
        # Hàm chạy các tác vụ chặn trong thread riêng
        async def run_in_executor(func, *args, **kwargs):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
        
        # Kiểm tra các trường hợp chuẩn trước
        standard_response = await run_in_executor(self.get_standard_response, message)
        if standard_response:
            return standard_response
        
        # Xử lý với LLM nếu không phải trường hợp chuẩn
        retries = 0
        while retries < self.max_retries:
            try:
                user_context_str = user_context if user_context else "Không có thông tin ngữ cảnh."
                
                # Sử dụng invoke trong thread riêng để không chặn event loop
                response = await run_in_executor(
                    self.chain.invoke,
                    {"input": message, "user_context": user_context_str}
                )
                
                return {
                    "type": "conversation",
                    "message": response.content.strip()
                }
            
            except Exception as e:
                retries += 1
                print(f"Lỗi (thử lại {retries}/{self.max_retries}): {str(e)}")
                if retries == self.max_retries:
                    return {
                        "type": "error",
                        "message": "Xin lỗi, tôi đang gặp vấn đề kỹ thuật. Vui lòng thử lại sau."
                    }
                await asyncio.sleep(1)
    
    def process_message(self, message, user_context=None):
        """
        Xử lý tin nhắn của người dùng và trả về phản hồi.
        
        Args:
            message (str): Tin nhắn của người dùng
            user_context (str, optional): Thông tin ngữ cảnh của người dùng
        Returns:
            Dict chứa loại và nội dung phản hồi
        """
        # Kiểm tra các trường hợp chuẩn trước
        standard_response = self.get_standard_response(message)
        if standard_response:
            return standard_response
        
        # Xử lý với LLM nếu không phải trường hợp chuẩn
        retries = 0
        while retries < self.max_retries:
            try:
                user_context_str = user_context if user_context else "Không có thông tin ngữ cảnh."
                
                # Sử dụng invoke thay vì run
                response = self.chain.invoke({"input": message, "user_context": user_context_str})
                
                return {
                    "type": "conversation",
                    "message": response.content.strip()
                }
            
            except Exception as e:
                retries += 1
                print(f"Lỗi (thử lại {retries}/{self.max_retries}): {str(e)}")
                if retries == self.max_retries:
                    return {
                        "type": "error",
                        "message": "Xin lỗi, tôi đang gặp vấn đề kỹ thuật. Vui lòng thử lại sau."
                    }
                time.sleep(1)

# Ví dụ sử dụng
if __name__ == "__main__":
    agent = ConversationAgent()
    
    # Danh sách các ví dụ để kiểm tra
    test_messages = [
        "mày biết đấm nhau không"
    ]
    
    for message in test_messages:
        print(f"\nNgười dùng: {message}")
        response = agent.process_message(message)
        print(f"Trợ lý ({response['type']}): {response['message']}")