import os 
from dotenv import load_dotenv
from typing import Optional
load_dotenv()

class Config:
    """Lớp cấu hình cho quá trình xử lý PDF và OCR"""
    
    def __init__(self, base_path=None):
        """Khởi tạo cấu hình với các đường dẫn và khóa API"""
        self.base_path = base_path or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.load_env_vars()
        self.setup_paths()
        
    def load_env_vars(self):
        """Tải biến môi trường từ .env file"""
        load_dotenv()
        self.mistral_api_key = os.environ.get("MISTRAL_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        
    def setup_paths(self):
        """Thiết lập các đường dẫn cho file và thư mục"""
        self.pdf_path = os.path.join(self.base_path, "data/AAPL.pdf")
        self.output_md_path = os.path.join(self.base_path, "data/ket_qua_ocr.md")
        self.temp_image_folder = os.path.join(self.base_path, "data/temp_images/")
        self.images_folder = os.path.join(self.base_path, "data/images/")
        
        for folder in [self.temp_image_folder, self.images_folder]:
            if not os.path.exists(folder):
                os.makedirs(folder)
                print(f"Đã tạo thư mục {folder}")