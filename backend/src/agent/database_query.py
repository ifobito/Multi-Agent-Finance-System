import psycopg2
import asyncio
import concurrent.futures
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import time
import os
from .configs.promtting import prompt_template_schema
class DatabaseQueryAgent:
    def __init__(self, host, port, dbname, user, password, model_name="gpt-4o-mini", max_retries=3):
        """Khởi tạo agent truy vấn cơ sở dữ liệu PostgreSQL.
        
        Args:
            host (str): Host của PostgreSQL
            port (str): Port của PostgreSQL
            dbname (str): Tên cơ sở dữ liệu
            user (str): Tên người dùng
            password (str): Mật khẩu
            model_name (str): Tên mô hình LLM (mặc định: gpt-4o-mini)
            max_retries (int): Số lần thử lại tối đa khi query lỗi
        """
        self.conn_params = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password
        }
        self.max_retries = max_retries
        self.llm = Chaturya = ChatOpenAI(
            model_name=model_name,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.prompt_template = PromptTemplate(
            input_variables=["question", "schema"],
            template="""
            Giả sử bạn là một chuyên gia về tạo câu query cho dữ liệu, dữ liệu của người dùng liên quan đến tài chính,nếu câu hỏi liên quan đến tính toán bạn phải viết thêm các hàm tính toán từ tài chính.
            Dựa trên schema cơ sở dữ liệu sau:
            {schema}

            Hãy tạo một câu query SQL chuẩn PostgreSQL để trả lời câu hỏi sau:
            {question}

            Chỉ trả về câu query SQL, không giải thích.
            """
        )
        self.chain = self.prompt_template | self.llm    

    # def get_schema(self):
    #     """Lấy schema của cơ sở dữ liệu."""
    #     try:
    #         conn = psycopg2.connect(**self.conn_params)
    #         cursor = conn.cursor()
    #         cursor.execute("""
    #             SELECT table_name, column_name, data_type
    #             FROM information_schema.columns
    #             WHERE table_schema = 'public'
    #             ORDER BY table_name, column_name;
    #         """)
    #         schema = ""
    #         current_table = ""
    #         for row in cursor.fetchall():
    #             table_name, column_name, data_type = row
    #             if table_name != current_table:
    #                 schema += f"\nTable: {table_name}\n"
    #                 current_table = table_name
    #             schema += f"  - {column_name} ({data_type})\n"
    #         conn.close()
    #         return schema
    #     except psycopg2.Error as e:
    #         raise Exception(f"Không thể lấy schema: {str(e)}")

    def generate_query(self, question):
        """Tạo câu query SQL từ câu hỏi người dùng."""
        schema = prompt_template_schema()
        response = self.chain.invoke({"question": question, "schema": schema})
        raw_query = response.content if hasattr(response, 'content') else str(response)
        
        clean_query = raw_query.replace('```sql', '').replace('```', '').strip()
        return clean_query

    def execute_query(self, query):
        """Thực thi câu query và trả về kết quả."""
        conn = psycopg2.connect(**self.conn_params)
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                results = cursor.fetchall()
            else:
                columns = []
                results = []
            conn.commit()
            conn.close()
            return columns, results
        except psycopg2.Error as e:
            conn.rollback()
            conn.close()
            raise Exception(f"Lỗi khi thực thi query: {str(e)}")

    async def query_with_retry_async(self, question):
        """
        Thực hiện truy vấn bất đồng bộ với cơ chế thử lại nếu lỗi.
        
        Args:
            question (str): Câu hỏi của người dùng
        Returns:
            Dict chứa query, columns và kết quả
        """
        # Hàm chạy các tác vụ chặn trong thread riêng
        async def run_in_executor(func, *args, **kwargs):
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return await loop.run_in_executor(
                    pool, lambda: func(*args, **kwargs)
                )
        
        retries = 0
        while retries < self.max_retries:
            try:
                # Sinh câu truy vấn bằng cách bất đồng bộ
                query = await run_in_executor(self.generate_query, question)
                print(f"Generated query: {query}")
                
                # Thực hiện truy vấn bằng cách bất đồng bộ
                columns, results = await run_in_executor(self.execute_query, query)
                
                formatted_results = [dict(zip(columns, row)) for row in results]
                return {
                    "query": query,
                    "columns": columns,
                    "results": formatted_results
                }
            except Exception as e:
                retries += 1
                print(f"Lỗi (thử lại {retries}/{self.max_retries}): {str(e)}")
                if retries == self.max_retries:
                    raise Exception(f"Đã thử {self.max_retries} lần nhưng vẫn thất bại: {str(e)}")
                await asyncio.sleep(1)
    
    def query_with_retry(self, question):
        """
        Thực hiện truy vấn với cơ chế thử lại nếu lỗi.
        
        Args:
            question (str): Câu hỏi của người dùng
        Returns:
            Dict chứa query, columns và kết quả
        """
        retries = 0
        while retries < self.max_retries:
            try:
                query = self.generate_query(question)
                print(f"Generated query: {query}")
                
                columns, results = self.execute_query(query)
                
                formatted_results = [dict(zip(columns, row)) for row in results]
                return {
                    "query": query,
                    "columns": columns,
                    "results": formatted_results
                }
            except Exception as e:
                retries += 1
                print(f"Lỗi (thử lại {retries}/{self.max_retries}): {str(e)}")
                if retries == self.max_retries:
                    raise Exception(f"Đã thử {self.max_retries} lần nhưng vẫn thất bại: {str(e)}")
                time.sleep(1) 

if __name__ == "__main__":
    agent = DatabaseQueryAgent(
        host="localhost",
        port="5432",
        dbname="postgres", 
        user="postgres",
        password="postgres"
    )
    question = "What was the closing price of Microsoft on March 15, 2024?"
    try:
        result = agent.query_with_retry(question)
        print("Kết quả truy vấn:", result)
    except Exception as e:
        print("Lỗi:", str(e))