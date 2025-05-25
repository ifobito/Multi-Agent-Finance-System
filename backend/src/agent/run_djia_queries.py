import json
import os
import time
import decimal
import datetime
from database_query import DatabaseQueryAgent

# Định nghĩa class JSONEncoder tùy chỉnh để xử lý các kiểu dữ liệu đặc biệt
class CustomJSONEncoder(json.JSONEncoder):
    """
    Lớp mã hóa JSON tùy chỉnh để xử lý các kiểu dữ liệu không được hỗ trợ sẵn trong JSON.
    
    Hiện tại hỗ trợ:
    - decimal.Decimal: chuyển thành float
    - datetime.date: chuyển thành chuỗi ISO format
    - datetime.datetime: chuyển thành chuỗi ISO format
    """
    def default(self, obj):
        # Xử lý kiểu dữ liệu Decimal
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        # Xử lý kiểu dữ liệu date
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        # Xử lý kiểu dữ liệu datetime
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        # Các kiểu dữ liệu khác có thể được thêm vào đây
        return super(CustomJSONEncoder, self).default(obj)

class DJIAQueryRunner:
    """
    Lớp thực hiện truy vấn các câu hỏi từ tập dữ liệu DJIA và lưu kết quả.
    
    Args:
        json_file_path (str): Đường dẫn đến file JSON chứa các câu hỏi
        db_config (dict): Thông tin cấu hình kết nối database
        output_file_path (str): Đường dẫn để lưu kết quả (mặc định là file gốc)
    """
    def __init__(self, json_file_path, db_config, output_file_path=None):
        self.json_file_path = json_file_path
        self.output_file_path = output_file_path or json_file_path
        self.db_config = db_config
        self.agent = DatabaseQueryAgent(
            host=db_config['host'],
            port=db_config['port'],
            dbname=db_config['dbname'],
            user=db_config['user'],
            password=db_config['password'],
            model_name=db_config.get('model_name', 'gpt-4o-mini'),
            max_retries=db_config.get('max_retries', 3)
        )
        
    def load_questions(self):
        """
        Đọc các câu hỏi từ file JSON.
        
        Returns:
            list: Danh sách các câu hỏi
        """
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"Lỗi khi đọc file JSON: {str(e)}")
    
    def save_results(self, data):
        """
        Lưu kết quả vào file JSON.
        
        Args:
            data (list): Dữ liệu cần lưu
        """
        try:
            with open(self.output_file_path, 'w', encoding='utf-8') as f:
                # Sử dụng class encoder tùy chỉnh để xử lý các kiểu dữ liệu đặc biệt như Decimal
                json.dump(data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            print(f"Đã lưu kết quả vào {self.output_file_path}")
        except Exception as e:
            raise Exception(f"Lỗi khi lưu file JSON: {str(e)}")
    
    def run_single_query(self, question_data):
        """
        Thực hiện một truy vấn đơn.
        
        Args:
            question_data (dict): Dữ liệu câu hỏi
            
        Returns:
            dict: Dữ liệu câu hỏi đã được bổ sung kết quả truy vấn
        """
        question = question_data['question']
        print(f"\nXử lý câu hỏi {question_data['number']}: {question}")
        
        try:
            start_time = time.time()
            result = self.agent.query_with_retry(question)
            end_time = time.time()
            
            # Thêm kết quả truy vấn vào dữ liệu câu hỏi
            question_data['query_result'] = {
                'sql_query': result['query'],
                'columns': result['columns'],
                'results': result['results'],
                'execution_time': round(end_time - start_time, 2)
            }
            
            # So sánh kết quả với câu trả lời gốc nếu có
            if 'answer' in question_data:
                question_data['query_result']['matches_expected'] = self._compare_results(
                    result['results'], question_data['answer']
                )
                
            # Thêm câu trả lời được rút ra từ kết quả truy vấn
            question_data['query_result']['extracted_answer'] = self._extract_answer_from_results(result['results'])
                
            print(f"Đã hoàn thành truy vấn trong {round(end_time - start_time, 2)} giây")
            return question_data
            
        except Exception as e:
            # Nếu có lỗi, vẫn lưu thông tin lỗi vào kết quả
            question_data['query_result'] = {
                'error': str(e),
                'success': False
            }
            print(f"Lỗi khi xử lý câu hỏi: {str(e)}")
            return question_data
    
    def _compare_results(self, results, expected_answer):
        """
        So sánh kết quả truy vấn với câu trả lời gốc.
        Phương thức này có thể được mở rộng để xử lý so sánh phức tạp hơn.
        
        Args:
            results (list): Kết quả từ truy vấn SQL
            expected_answer (str): Câu trả lời mong đợi
            
        Returns:
            bool: True nếu kết quả khớp với câu trả lời mong đợi
        """
        # Đây là một phương pháp so sánh đơn giản
        # Có thể cần phát triển thuật toán phức tạp hơn tùy theo định dạng dữ liệu
        if not results:
            return False
            
        # Chuyển đổi kết quả sang chuỗi để so sánh
        result_str = str(results[0])
        
        # Xóa các ký tự không cần thiết để so sánh
        expected_clean = expected_answer.replace('$', '').replace(',', '').lower()
        result_clean = result_str.replace('$', '').replace(',', '').lower()
        
        # Kiểm tra nếu kết quả mong đợi có trong kết quả truy vấn
        return expected_clean in result_clean
        
    def _extract_answer_from_results(self, results):
        """
        Trích xuất câu trả lời có định dạng từ kết quả truy vấn.
        
        Args:
            results (list): Kết quả từ truy vấn SQL
            
        Returns:
            str: Câu trả lời định dạng
        """
        if not results or not isinstance(results, list) or len(results) == 0:
            return "Không có kết quả"
        
        # Lấy giá trị đầu tiên từ kết quả đầu tiên
        first_result = results[0]
        if isinstance(first_result, dict) and len(first_result) > 0:
            # Nếu là dictionary, lấy giá trị đầu tiên
            key = list(first_result.keys())[0]
            value = first_result[key]
        else:
            # Nếu không phải dictionary, sử dụng giá trị đó
            value = first_result
            
        # Định dạng giá trị dựa trên loại dữ liệu
        if isinstance(value, (int, float, decimal.Decimal)):
            # Nếu là số, định dạng theo tiền tệ nếu có vẻ là giá cổ phiếu
            if 0 < float(value) < 10000:
                return f"${float(value):.2f}"
            else:
                return f"{float(value):,.0f}"
        elif isinstance(value, str):
            return value
        else:
            return str(value)
    
    def run_all_queries(self, start_index=0, limit=None, save_after_each=True):
        """
        Thực hiện tất cả các truy vấn trong file JSON.
        
        Args:
            start_index (int): Chỉ số bắt đầu (để tiếp tục từ lần chạy trước)
            limit (int): Số lượng câu hỏi tối đa cần xử lý
            save_after_each (bool): Lưu kết quả sau mỗi truy vấn
            
        Returns:
            list: Danh sách các câu hỏi đã được bổ sung kết quả
        """
        data = self.load_questions()
        total = len(data)
        
        end_index = total if limit is None else min(start_index + limit, total)
        
        print(f"Bắt đầu xử lý {end_index - start_index} câu hỏi (từ {start_index+1} đến {end_index})")
        
        for i in range(start_index, end_index):
            data[i] = self.run_single_query(data[i])
            
            if save_after_each:
                self.save_results(data)
                print(f"Đã lưu tiến trình ({i+1}/{total})")
        
        if not save_after_each:
            self.save_results(data)
            
        return data
        
    def run_filtered_queries(self, filter_func, save_after_each=True):
        """
        Thực hiện các truy vấn được lọc bởi hàm filter.
        
        Args:
            filter_func (callable): Hàm để lọc các câu hỏi cần xử lý
            save_after_each (bool): Lưu kết quả sau mỗi truy vấn
            
        Returns:
            list: Danh sách các câu hỏi đã được bổ sung kết quả
        """
        data = self.load_questions()
        filtered_indices = [i for i, q in enumerate(data) if filter_func(q)]
        total = len(filtered_indices)
        
        print(f"Đã lọc {total} câu hỏi để xử lý")
        
        for idx, i in enumerate(filtered_indices):
            data[i] = self.run_single_query(data[i])
            
            if save_after_each:
                self.save_results(data)
                print(f"Đã lưu tiến trình ({idx+1}/{total})")
        
        if not save_after_each and total > 0:
            self.save_results(data)
            
        return data


if __name__ == "__main__":
    # Cấu hình kết nối database
    db_config = {
        'host': 'localhost',
        'port': '5432',
        'dbname': 'postgres',
        'user': 'postgres',
        'password': 'postgres',
        'model_name': 'gpt-4o-mini',
        'max_retries': 3
    }
    
    # Đường dẫn đến file JSON
    json_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                 'data', 'djia_qna.json')
    
    # Tạo đường dẫn file kết quả (có thể chọn lưu sang file mới)
    output_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                   'data', 'djia_qna_results.json')
    
    # Khởi tạo đối tượng để chạy truy vấn
    runner = DJIAQueryRunner(
        json_file_path=json_file_path,
        db_config=db_config,
        output_file_path=output_file_path  # Nếu muốn lưu vào file gốc, bỏ dòng này
    )
    
    # Chạy tất cả 100 câu hỏi
    print("Bắt đầu xử lý tất cả 100 câu hỏi...")
    runner.run_all_queries(save_after_each=True)
    
    # Các tùy chọn khác (đã bị comment out)
    # Chạy một số câu hỏi đầu tiên
    # runner.run_all_queries(start_index=0, limit=5)
    
    # Hoặc chạy các câu hỏi theo loại
    # runner.run_filtered_queries(
    #     filter_func=lambda q: q['type'] == 'factual' and q['complexity'] == 'easy',
    #     save_after_each=True
    # )
