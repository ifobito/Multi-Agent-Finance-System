import os
import json
from langchain_tavily import TavilySearch
from dotenv import load_dotenv
import time
from datetime import datetime

class GoogleSearchAgent:
    def __init__(self, api_key=None, max_retries=3, max_results=3):
        """Khởi tạo agent tìm kiếm trên web.
        
        Args:
            api_key (str): Khóa API Tavily (nếu không cung cấp sẽ lấy từ biến môi trường)
            max_retries (int): Số lần thử lại tối đa khi tìm kiếm lỗi
            max_results (int): Số kết quả tối đa trả về từ mỗi lần tìm kiếm (mặc định: 3)
        """
        load_dotenv()
        
        self.tavily_api_key = api_key or os.getenv("TAVILY_API_KEY")
        
        self.search = TavilySearch(
            api_key=self.tavily_api_key,
            max_results=max_results,
            search_depth="advanced"
        )
        
        self.max_retries = max_retries
        self.max_results = max_results

    def search_with_retry(self, query):
        """Thực hiện tìm kiếm với cơ chế thử lại nếu lỗi."""
        retries = 0
        while retries < self.max_retries:
            try:

                search_response = self.search.invoke(query)
                if isinstance(search_response, dict):
                    search_results = search_response.get('results', [])
                elif isinstance(search_response, list):
                    search_results = search_response
                else:
                    search_results = []
                
                if not search_results:
                    return {
                        "status": "no_results",
                        "message": "Không tìm thấy kết quả nào."
                    }
                
                if len(search_results) > 0:
                    first_result = search_results[0]
                    if isinstance(first_result, dict):
                        for key, value in first_result.items():
                            print(f"  - {key}: {str(value)[:100]}...")
                
                simplified_results = []
                for i, item in enumerate(search_results):
                    print(f"Xử lý kết quả #{i+1}, kiểu: {type(item)}")
                    if isinstance(item, dict):
                        result_item = {
                            "title": item.get("title", "Không có tiêu đề"),
                            "content": item.get("content", "Không có nội dung"),
                            "url": item.get("url", "Không có URL")
                        }
                        simplified_results.append(result_item)
                        print(f"  - Đã thêm: {result_item['title'][:50]}...")
                    else:
                        print(f"  - Bỏ qua: không phải dict")
                
                # Kiểm tra xem có kết quả nào sau khi lọc không
                if not simplified_results:
                    print("Không có kết quả nào sau khi lọc!")
                    return {
                        "status": "no_results",
                        "message": "Không thể xử lý kết quả tìm kiếm."
                    }
                
                print(f"Đã xử lý thành công {len(simplified_results)} kết quả")
                return {
                    "status": "success",
                    "query": query,
                    "results": simplified_results,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
            except Exception as e:
                retries += 1
                print(f"Lỗi (thử lại {retries}/{self.max_retries}): {str(e)}")
                if retries == self.max_retries:
                    return {
                        "status": "error",
                        "message": f"Đã thử {self.max_retries} lần nhưng vẫn thất bại: {str(e)}"
                    }
                time.sleep(1)

    def get_latest_stock_price(self, symbol):
        """Tìm giá cổ phiếu mới nhất cho một mã cổ phiếu cụ thể."""
        query = f"giá cổ phiếu {symbol} hiện tại mới nhất"
        return self.search_with_retry(query)
    
    def get_company_news(self, company_name):
        """Tìm tin tức mới nhất về một công ty."""
        query = f"tin tức mới nhất về công ty {company_name}"
        return self.search_with_retry(query)
    
    def get_market_trends(self):
        """Tìm xu hướng thị trường chứng khoán hiện tại."""
        query = "xu hướng thị trường chứng khoán hiện tại"
        return self.search_with_retry(query)

# Ví dụ sử dụng
if __name__ == "__main__":
    # Thiết lập biến môi trường cho API key nếu chưa có trong .env
    # os.environ["TAVILY_API_KEY"] = "your-tavily-api-key"
    
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        print("CẢNH BÁO: TAVILY_API_KEY không được tìm thấy trong biến môi trường.")
        print("Vui lòng thêm vào file .env:")
        print("TAVILY_API_KEY=your_api_key_here")
        print("\nHoặc bạn có thể thêm trực tiếp trong code:")
        print("agent = GoogleSearchAgent(api_key='your_api_key_here')")
        print("\nBạn có thể đăng ký API key miễn phí tại: https://tavily.com")
        exit(1)
    
    agent = GoogleSearchAgent()
    
    # Ví dụ tìm kiếm
    query = "Which sector does Chevron belong to?"
    
    try:
        result = agent.search_with_retry(query)
        
        if result["status"] == "success":
            print("\n=== Kết quả tìm kiếm ===")
            print(f"Câu truy vấn: {result['query']}")
            print(f"Thời gian: {result['timestamp']}\n")
            
            print("Chi tiết:")
            for i, item in enumerate(result['results'], 1):
                print(f"{i}. {item['title']}")
                print(f"   URL: {item['url']}")
                print(f"   Nội dung: {item['content']}\n")
        else:
            print(f"\n=== Lỗi ===\n{result.get('message', 'Không xác định')}")
    
    except Exception as e:
        print(f"Lỗi không mong đợi: {str(e)}")