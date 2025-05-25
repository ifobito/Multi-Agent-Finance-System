from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
import logging
from langchain_core.documents import Document
from dotenv import load_dotenv
import os

load_dotenv()
logger = logging.getLogger(__name__)

class OpenAIEmbedding:
    """
    Lớp tạo vector embedding sử dụng OpenAI API thông qua LangChain.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-large"):
        """
        Khởi tạo OpenAIEmbeddings client qua LangChain.
        
        Args:
            api_key: API key của OpenAI, mặc định lấy từ biến môi trường OPENAI_API_KEY
            model: Tên model embedding, mặc định là text-embedding-3-large
        """
        self.api_key = api_key
        self.model = model
        self.dimensions = 3072
        
        self.embeddings = OpenAIEmbeddings(
            model=self.model,
            api_key=self.api_key,
            dimensions=self.dimensions
        )
        logger.info(f"Đã khởi tạo OpenAIEmbeddings với model: {model} ({self.dimensions} chiều)")
        
    def create_embedding(self, text) -> List[float]:
        """
        Tạo vector embedding cho văn bản.
        
        Args:
            text: Văn bản cần tạo embedding (str hoặc Document)
            
        Returns:
            Vector embedding dưới dạng list float
        """
        try:
            # Xử lý input là Document hoặc có page_content
            if isinstance(text, Document):
                text_content = text.page_content
            elif hasattr(text, 'page_content'):
                text_content = getattr(text, 'page_content', '')
            elif isinstance(text, dict) and 'page_content' in text:
                text_content = text['page_content']
            else:
                text_content = str(text)
                
            # Giới hạn độ dài văn bản
            if len(text_content) > 8000:
                logger.warning(f"Văn bản quá dài ({len(text_content)} ký tự), cắt bớt xuống 8000 ký tự")
                text_content = text_content[:8000]
                
            # Tạo embedding sử dụng LangChain
            embedding = self.embeddings.embed_query(text_content)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo embedding: {e}")
            raise