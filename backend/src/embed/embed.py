import os
from typing import Iterable
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
import uuid
from dotenv import load_dotenv

load_dotenv()

# Cấu hình Elasticsearch và OpenAI
es_url = "http://localhost:9200"
index_name = "test-langchain-retriever"
text_field = "text"
dense_vector_field = "embedding"
num_characters_field = "num_characters"
metadata_field = "metadata"
api_key = os.getenv("OPENAI_API_KEY")

# Khởi tạo Elasticsearch và Embeddings
es_client = Elasticsearch(hosts=[es_url])
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=api_key)

def read_markdown_file(file_path: str) -> str:
    """Đọc nội dung file Markdown."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Không tìm thấy file: {file_path}")
        return ""
    except Exception as e:
        print(f"Lỗi khi đọc file: {e}")
        return ""

def split_markdown_content(markdown_content: str) -> list[Document]:
    """Tách nội dung Markdown thành các đoạn với metadata."""
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=True
    )
    return markdown_splitter.split_text(markdown_content)

def create_index(
    es_client: Elasticsearch,
    index_name: str,
    text_field: str,
    dense_vector_field: str,
    num_characters_field: str,
    metadata_field: str,
):
    """Tạo chỉ mục Elasticsearch với các trường text, dense_vector, integer và metadata."""
    es_client.indices.delete(index=index_name, ignore=[404])
    es_client.indices.create(
        index=index_name,
        mappings={
            "properties": {
                text_field: {"type": "text"},
                dense_vector_field: {"type": "dense_vector", "dims": 3072},
                num_characters_field: {"type": "integer"},
                metadata_field: {"type": "object", "enabled": True},
            }
        },
    )

def index_data(
    es_client: Elasticsearch,
    index_name: str,
    text_field: str,
    dense_vector_field: str,
    num_characters_field: str,
    metadata_field: str,
    embeddings: OpenAIEmbeddings,
    documents: Iterable[Document],
    refresh: bool = True,
) -> int:
    """Lập chỉ mục dữ liệu vào Elasticsearch với embeddings và metadata."""
    create_index(es_client, index_name, text_field, dense_vector_field, num_characters_field, metadata_field)
    
    texts = [doc.page_content for doc in documents]
    vectors = embeddings.embed_documents(texts)
    
    requests = [
        {
            "_op_type": "index",
            "_index": index_name,
            "_id": str(uuid.uuid4()),
            text_field: doc.page_content,
            dense_vector_field: vector,
            num_characters_field: len(doc.page_content),
            metadata_field: doc.metadata,
        }
        for doc, vector in zip(documents, vectors)
    ]
    
    bulk(es_client, requests)
    
    if refresh:
        es_client.indices.refresh(index=index_name)
    
    return len(requests)

def main():
    try:
        # Đường dẫn đến file Markdown
        file_path = "/Users/obito/Documents/year4/Data platforms/Information-System-of-the-Official-Agent-Using-LangGraph/data/readme.md"
        
        # Đọc và tách nội dung Markdown
        markdown_content = read_markdown_file(file_path)
        if not markdown_content:
            print("Không thể đọc nội dung file Markdown.")
            return
        
        documents = split_markdown_content(markdown_content)
        if not documents:
            print("Không tách được nội dung từ file Markdown.")
            return
        
        # Lập chỉ mục dữ liệu
        num_indexed = index_data(
            es_client,
            index_name,
            text_field,
            dense_vector_field,
            num_characters_field,
            metadata_field,
            embeddings,
            documents,
        )
        print(f"Đã lập chỉ mục thành công {num_indexed} tài liệu.")
    except Exception as e:
        print(f"Lỗi khi lập chỉ mục dữ liệu: {e}")

if __name__ == "__main__":
    main()