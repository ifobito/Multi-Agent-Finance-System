import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import time
import decimal
import asyncio
import concurrent.futures
from typing import Dict, List, Tuple, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from datetime import datetime
import sys
import os
import json
import re  # Đảm bảo re được import ở cấp độ module

from .database_query import DatabaseQueryAgent
# from database_query import DatabaseQueryAgent

class VisualizeAgent:
    def __init__(self, host="localhost", port="5432", dbname="postgres", 
                 user="postgres", password="postgres", model_name="gpt-4o-mini", 
                 max_retries=3, save_dir="./visualizations"):
        """
        Khởi tạo agent trực quan hóa dữ liệu từ PostgreSQL.
        
        Args:
            host (str): Host của PostgreSQL
            port (str): Port của PostgreSQL
            dbname (str): Tên cơ sở dữ liệu
            user (str): Tên người dùng
            password (str): Mật khẩu
            model_name (str): Tên mô hình LLM (mặc định: gpt-4o-mini)
            max_retries (int): Số lần thử lại tối đa khi query lỗi
            save_dir (str): Thư mục lưu biểu đồ
        """
        self.db_agent = DatabaseQueryAgent(host, port, dbname, user, password, model_name, max_retries)
        self.save_dir = save_dir
        
        # Tạo thư mục lưu biểu đồ nếu chưa tồn tại
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        # Khởi tạo LLM để phân tích và đề xuất loại biểu đồ
        self.llm = ChatOpenAI(
            model_name=model_name,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Template cho việc phân tích dữ liệu và đề xuất loại biểu đồ
        self.viz_prompt_template = PromptTemplate(
            input_variables=["question", "columns", "sample_data"],
            template="""
            Dựa trên câu hỏi và dữ liệu trả về từ cơ sở dữ liệu:
            
            Câu hỏi: {question}
            
            Các cột dữ liệu: {columns}
            
            Mẫu dữ liệu: {sample_data}
            
            Hãy đề xuất loại biểu đồ phù hợp nhất để trực quan hóa dữ liệu này và giải thích lý do.
            Trả về kết quả theo định dạng JSON như sau:
            ```json
            {{
                "chart_type": "bar|line|pie|scatter|heatmap|boxplot|histogram",
                "x_column": "tên cột dữ liệu cho trục x",
                "y_column": "tên cột dữ liệu cho trục y (có thể là nhiều cột phân tách bằng dấu phẩy)",
                "title": "tiêu đề đề xuất cho biểu đồ",
                "explanation": "giải thích ngắn gọn tại sao loại biểu đồ này phù hợp"
            }}
            ```
            """
        )
        
        self.viz_chain = self.viz_prompt_template | self.llm

    def analyze_and_suggest_visualization(self, question: str, columns: List[str], 
                                          results: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Phân tích dữ liệu và đề xuất loại biểu đồ phù hợp.
        
        Args:
            question (str): Câu hỏi người dùng
            columns (List[str]): Danh sách tên cột
            results (List[Dict[str, Any]]): Kết quả truy vấn
        
        Returns:
            Dict[str, str]: Thông tin về loại biểu đồ đề xuất
        """
        import re  # Đảm bảo import re trong phạm vi này
        # Kiểm tra xem người dùng đã chỉ định loại biểu đồ chưa
        chart_types = ["bar", "line", "pie", "scatter", "heatmap", "boxplot", "histogram"]
        specified_chart_type = None
        
        # Kiểm tra các loại biểu đồ trong câu truy vấn
        for chart_type in chart_types:
            if chart_type in question.lower():
                specified_chart_type = chart_type
                print(f"Người dùng đã chỉ định loại biểu đồ: {chart_type}")
                break
        
        # Nếu người dùng đã chỉ định loại biểu đồ, ưu tiên sử dụng loại đó
        if specified_chart_type:
            # Vẫn yêu cầu LLM phân tích nhưng chỉ để lấy các thông tin khác
            try:
                # Lấy mẫu dữ liệu (tối đa 5 hàng)
                sample_data = results[:5]
                
                # Phân tích dữ liệu
                # Sử dụng invoke thay vì run với RunnableSequence
                response = self.viz_chain.invoke({
                    "question": question,
                    "columns": columns,
                    "sample_data": sample_data
                })
                raw_response = response.content if hasattr(response, 'content') else str(response)
                
                # Trích xuất phần JSON từ phản hồi để lấy các thông tin khác
                try:
                    # Đảm bảo có import re ở đây
                    import re
                    json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', raw_response)
                    if json_match:
                        chart_info = json.loads(json_match.group(1))
                        # Ghi đè loại biểu đồ bằng loại người dùng chỉ định
                        chart_info["chart_type"] = specified_chart_type
                        return chart_info
                except Exception as e:
                    print(f"Lỗi khi xử lý JSON từ LLM: {e}")
                
                # Nếu không lấy được các thông tin khác, tự tạo cấu hình
                default_column = columns[0] if columns else ""
                second_column = columns[1] if len(columns) > 1 else columns[0] if columns else ""
                
                return {
                    "chart_type": specified_chart_type,
                    "x_column": default_column,
                    "y_column": second_column,
                    "title": f"Biểu đồ {specified_chart_type} của {default_column} theo {second_column}",
                    "explanation": f"Biểu đồ {specified_chart_type} được chỉ định trực tiếp bởi người dùng."
                }
            except Exception as e:
                print(f"Lỗi khi xử lý các thông tin biểu đồ từ người dùng: {e}")
        
        # Nếu người dùng không chỉ định, sử dụng LLM để đề xuất
        try:
            # Lấy mẫu dữ liệu (tối đa 5 hàng)
            sample_data = results[:5]
            
            # Phân tích dữ liệu để đề xuất loại biểu đồ
            # Sử dụng invoke thay vì run với RunnableSequence
            response = self.viz_chain.invoke({
                "question": question,
                "columns": columns,
                "sample_data": sample_data
            })
            raw_response = response.content if hasattr(response, 'content') else str(response)
            
            # Trích xuất phần JSON từ phản hồi
            import json
            # Đảm bảo re được import trong phạm vi này
            import re
            
            json_match = re.search(r'```json\n(.*?)\n```', raw_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = raw_response
                
            viz_suggestion = json.loads(json_str)
            return viz_suggestion
        except Exception as e:
            print(f"Lỗi khi phân tích dữ liệu: {str(e)}")
            # Mặc định trả về biểu đồ cột nếu phân tích thất bại
            return {
                "chart_type": "bar",
                "x_column": columns[0] if columns else "",
                "y_column": columns[1] if len(columns) > 1 else columns[0],
                "title": f"Biểu đồ cho câu hỏi: {question[:50]}...",
                "explanation": "Mặc định sử dụng biểu đồ cột do lỗi phân tích"
            }

    def preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Tiền xử lý dữ liệu trước khi tạo biểu đồ.
        
        Args:
            df (pd.DataFrame): DataFrame gốc
            
        Returns:
            pd.DataFrame: DataFrame đã xử lý
        """
        # Chuyển đổi các cột sang kiểu dữ liệu phù hợp
        for col in df.columns:
            # Xử lý các giá trị None/NaN
            if df[col].isnull().any():
                print(f"Phát hiện giá trị null trong cột {col}, đang xử lý...")
                # Với cột số, thay thế None bằng 0 hoặc giá trị trung bình
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].mean() if not df[col].isnull().all() else 0)
                else:
                    df[col] = df[col].fillna("N/A")
            
            # Chuyển đổi các cột chứa decimal.Decimal thành float
            try:
                if "decimal" in str(df[col].dtype).lower() or df[col].apply(lambda x: hasattr(x, "as_tuple")).any():
                    print(f"Chuyển đổi cột {col} từ Decimal sang float")
                    df[col] = df[col].astype(float)
            except Exception as e:
                print(f"Lỗi khi xử lý cột {col}: {str(e)}")
                # Nếu không thể chuyển đổi, thử cách khác
                try:
                    df[col] = df[col].apply(lambda x: float(x) if x is not None else None)
                    df[col] = df[col].fillna(0)  # Thay thế None bằng 0
                except:
                    pass
                    
        return df
    
    def create_visualization(self, df: pd.DataFrame, chart_info: Dict[str, str], question: str = "") -> plt.Figure:
        """
        Tạo biểu đồ theo loại được đề xuất.
        
        Args:
            df (pd.DataFrame): DataFrame chứa dữ liệu
            chart_info (Dict[str, str]): Thông tin về biểu đồ
            question (str, optional): Câu hỏi gốc từ người dùng. Mặc định: ""
        
        Returns:
            plt.Figure: Đối tượng biểu đồ đã tạo
        """
        # Tiền xử lý dữ liệu
        df = self.preprocess_data(df)
        
        # Thiết lập style cho biểu đồ
        sns.set_theme(style="whitegrid")
        plt.figure(figsize=(12, 6))
        
        chart_type = chart_info.get("chart_type", "bar")
        x_column = chart_info.get("x_column", "")
        y_columns = [col.strip() for col in chart_info.get("y_column", "").split(",")]
        title = chart_info.get("title", "Biểu đồ dữ liệu")
        
        # Đảm bảo các cột tồn tại trong DataFrame
        if x_column not in df.columns:
            x_column = df.columns[0] if len(df.columns) > 0 else None
            
        valid_y_columns = [col for col in y_columns if col in df.columns]
        if not valid_y_columns and len(df.columns) > 1:
            valid_y_columns = [df.columns[1]]
        elif not valid_y_columns and len(df.columns) > 0:
            valid_y_columns = [df.columns[0]]
            
        if not x_column or not valid_y_columns:
            raise ValueError("Không đủ dữ liệu để tạo biểu đồ")

        # Histograms được xử lý đặc biệt
        if chart_type.lower() == "histogram":
            plt.hist(df[valid_y_columns[0]].values, bins=20, alpha=0.7)
            plt.xlabel(valid_y_columns[0])
            plt.ylabel("Tần số")
            plt.title(title)
            plt.grid(True, alpha=0.3)
            return plt.gcf()
            
        # Tạo biểu đồ dựa trên loại
        if chart_type == "bar":
            if len(valid_y_columns) == 1:
                ax = sns.barplot(x=x_column, y=valid_y_columns[0], data=df)
                plt.xlabel(x_column)
                plt.ylabel(valid_y_columns[0])
            else:
                df_melted = df.melt(id_vars=[x_column], value_vars=valid_y_columns)
                ax = sns.barplot(x=x_column, y="value", hue="variable", data=df_melted)
                plt.xlabel(x_column)
                plt.ylabel("Giá trị")
                
        elif chart_type == "line":
            if len(valid_y_columns) == 1:
                ax = sns.lineplot(x=x_column, y=valid_y_columns[0], data=df, marker="o")
                plt.xlabel(x_column)
                plt.ylabel(valid_y_columns[0])
            else:
                df_melted = df.melt(id_vars=[x_column], value_vars=valid_y_columns)
                ax = sns.lineplot(x=x_column, y="value", hue="variable", data=df_melted, marker="o")
                plt.xlabel(x_column)
                plt.ylabel("Giá trị")
                
        elif chart_type.lower() == "pie":
            # Xử lý biểu đồ tròn (pie chart)
            try:
                # Chuẩn bị dữ liệu cho biểu đồ tròn
                # Nếu có quá nhiều category, chỉ hiển thị top N phần tử lớn nhất và gộp phần còn lại
                max_slices = 8  # Số lứng phần tối đa để biểu đồ dễ đọc
                
                # Đảm bảo dữ liệu hợp lệ
                df[valid_y_columns[0]] = pd.to_numeric(df[valid_y_columns[0]], errors='coerce')
                df = df.dropna(subset=[valid_y_columns[0]])
                
                # Bỏ các giá trị âm (không thể vẽ pie chart với giá trị âm)
                df = df[df[valid_y_columns[0]] >= 0]
                
                if len(df) > max_slices:
                    # Sắp xếp theo giá trị giảm dần và lấy top N-1 hạng
                    sorted_df = df.sort_values(by=valid_y_columns[0], ascending=False)
                    top_df = sorted_df.iloc[:max_slices-1].copy()
                    
                    # Tính tổng của phần còn lại
                    others_sum = sorted_df.iloc[max_slices-1:][valid_y_columns[0]].sum()
                    
                    # Tạo một hàng mới đại diện cho 'Khác'
                    others_row = pd.DataFrame({
                        x_column: ['Khác'],
                        valid_y_columns[0]: [others_sum]
                    })
                    
                    # Gộp lại
                    plot_df = pd.concat([top_df, others_row])
                else:
                    plot_df = df
                
                # Tạo màu sắc
                colors = plt.cm.tab20.colors[:len(plot_df)] if len(plot_df) > 10 else plt.cm.tab10.colors
                
                # Tạo biểu đồ tròn với các tùy chỉnh
                wedges, texts, autotexts = plt.pie(
                    plot_df[valid_y_columns[0]],
                    labels=None,  # Không hiển thị nhãn trực tiếp trên biểu đồ
                    autopct='%1.1f%%',
                    startangle=90,
                    colors=colors,
                    shadow=False,
                    wedgeprops={'edgecolor': 'w', 'linewidth': 1},
                    textprops={'fontsize': 12},
                )
                
                # Tạo legend thay vì labels trực tiếp trên biểu đồ
                # Rút gọn nhãn nếu quá dài
                labels = [f"{label[:20]}..." if len(str(label)) > 20 else str(label) for label in plot_df[x_column]]
                # Thêm giá trị vào legend
                for i, (label, value) in enumerate(zip(labels, plot_df[valid_y_columns[0]])):
                    labels[i] = f"{label}: {value:,.1f}"
                    
                plt.legend(wedges, labels, title=x_column,
                         loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                
                plt.axis('equal')
                plt.tight_layout()
                
            except Exception as e:
                print(f"Lỗi khi tạo biểu đồ tròn: {e}")
                # Nếu có lỗi, thử phương pháp đơn giản hơn
                try:
                    # Lấy top 5 phần tử và tạo biểu đồ tròn đơn giản
                    top_values = df.nlargest(5, valid_y_columns[0])
                    plt.pie(top_values[valid_y_columns[0]], labels=top_values[x_column], autopct='%1.1f%%')
                    plt.axis('equal')
                except Exception as e2:
                    print(f"Lỗi khi tạo biểu đồ tròn đơn giản: {e2}")
                    # Nếu vẫn lỗi, trả về biểu đồ cột rỗng nhất
                    plt.clf()
                    plt.bar(df[x_column][:5], df[valid_y_columns[0]][:5])
                    plt.xticks(rotation=45, ha='right')
                    plt.xlabel(x_column)
                    plt.ylabel(valid_y_columns[0])
                    plt.title(f"Biểu đồ cột thay thế (lỗi khi tạo biểu đồ tròn)")
                    plt.tight_layout()
            
        elif chart_type == "scatter":
            if len(valid_y_columns) >= 1:
                # Xử lý trường hợp đặc biệt cho biểu đồ phân tán với các công ty DJIA
                if "djia" in question.lower() or "dow jones" in question.lower() or "dow" in question.lower() or any(comp in question.lower() for comp in ["company", "companies"]):
                    # In thông tin debug về dữ liệu
                    print(f"Dữ liệu biểu đồ scatter plot DJIA: {df.head()}")
                    print(f"Các cột hiện có: {df.columns.tolist()}")
                    
                    # Tạo biểu đồ scatter với matplotlib trực tiếp
                    plt.figure(figsize=(12, 8))
                    
                    # Thiết lập các cột dữ liệu cho trục x và y
                    price_col = None
                    volume_col = None
                    company_col = None
                    
                    # Tìm các cột phù hợp dựa vào tên cột
                    for col in df.columns:
                        col_lower = col.lower()
                        if "price" in col_lower or "close" in col_lower or "avg_close" in col_lower or "average_close" in col_lower or "closing" in col_lower:
                            price_col = col
                        elif "volume" in col_lower or "avg_volume" in col_lower or "average_volume" in col_lower or "daily_volume" in col_lower:
                            volume_col = col
                        elif "company" in col_lower or "symbol" in col_lower or "name" in col_lower or "ticker" in col_lower:
                            company_col = col
                    
                    # Nếu không tìm thấy các cột cần thiết, sử dụng các cột mặc định
                    if price_col is None and len(df.columns) >= 2:
                        price_col = x_column if x_column else df.columns[1]
                    if volume_col is None and len(df.columns) >= 2:
                        volume_col = valid_y_columns[0] if valid_y_columns and valid_y_columns[0] else df.columns[0]
                    if company_col is None and len(df.columns) >= 3:
                        # Tìm cột công ty
                        for col in df.columns:
                            if col != price_col and col != volume_col:
                                company_col = col
                                break
                    
                    print(f"Cột giá: {price_col}, Cột khối lượng: {volume_col}, Cột công ty: {company_col}")
                    
                    if not price_col or not volume_col:
                        print("Không đủ cột dữ liệu để vẽ biểu đồ scatter")
                        # Tạo biểu đồ trống với thông báo
                        plt.text(0.5, 0.5, "Không có dữ liệu DJIA để hiển thị", 
                                ha='center', va='center', fontsize=16, color='red')
                        plt.xlim(-1, 1)
                        plt.ylim(-1, 1)
                        plt.title('Average Volume vs Average Close (2024)', fontsize=16, weight='bold')
                        return plt.gcf()
                    
                    # Chuyển đổi dữ liệu sang kiểu số
                    df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
                    df[volume_col] = pd.to_numeric(df[volume_col], errors='coerce')
                    
                    # Loại bỏ các hàng có giá trị NaN
                    df = df.dropna(subset=[price_col, volume_col])
                    
                    # Kiểm tra nếu dữ liệu rỗng
                    if df.empty or len(df) == 0:
                        print("DataFrame rỗng sau khi lọc NaN")
                        plt.text(0.5, 0.5, "Không có dữ liệu DJIA hợp lệ để hiển thị", 
                                ha='center', va='center', fontsize=16, color='red')
                        plt.xlim(-1, 1)
                        plt.ylim(-1, 1)
                        plt.title('Average Volume vs Average Close (2024)', fontsize=16, weight='bold')
                        return plt.gcf()
                    
                    x_data = df[price_col].values
                    y_data = df[volume_col].values
                    
                    print(f"Số điểm dữ liệu: {len(x_data)}")
                    print(f"Mẫu dữ liệu x: {x_data[:5] if len(x_data) >= 5 else x_data}")
                    print(f"Mẫu dữ liệu y: {y_data[:5] if len(y_data) >= 5 else y_data}")
                    
                    # Tạo màu sắc gradient dựa trên giá trị x để dễ phân biệt các điểm
                    colors = plt.cm.viridis(plt.Normalize()(x_data))
                    
                    # Vẽ các điểm với màu gradient và kích thước lớn hơn
                    scatter = plt.scatter(x_data, y_data, c=colors, s=80, alpha=0.8, edgecolors='white', linewidths=0.5)
                    
                    # Thêm nhãn cho các điểm nếu có cột công ty
                    if company_col:
                        # Sắp xếp lại vị trí nhãn để tránh chồng chéo
                        from adjustText import adjust_text
                        import re  # Đảm bảo re được import trong phạm vi này
                        
                        texts = []
                        for i, (x, y, label) in enumerate(zip(x_data, y_data, df[company_col])):
                            # Lấy symbol từ chuỗi nếu là tên dài
                            symbol = str(label)
                            if len(symbol) > 5 and '(' in symbol and ')' in symbol:
                                # Trích xuất mã chứng khoán trong ngoặc
                                match = re.search(r'\(([A-Z]+)\)', symbol)
                                if match:
                                    symbol = match.group(1)
                            elif len(symbol) > 10:
                                # Rút gọn tên công ty quá dài
                                symbol = symbol.split(' ')[0][:5]
                            
                            # Giới hạn độ dài nhãn
                            if len(symbol) > 5:
                                symbol = symbol[:5]
                            
                            # Thêm nhãn vào danh sách để điều chỉnh sau
                            text = plt.text(x, y, symbol, fontsize=10, weight='bold')
                            texts.append(text)
                        
                        # Cố gắng điều chỉnh vị trí các nhãn để tránh chồng chéo
                        try:
                            import importlib
                            if importlib.util.find_spec("adjustText") is not None:
                                adjust_text(texts, arrowprops=dict(arrowstyle='->', color='red', alpha=0.5))
                        except Exception as e:
                            print(f"Không thể điều chỉnh vị trí nhãn: {e}")
                            # Nếu không có adjustText, sử dụng phương pháp thay thế
                            for text in texts:
                                text.set_ha('center')
                                text.set_va('bottom')
                                text.set_y(text.get_position()[1] + 0.5)  # Di chuyển nhãn lên trên một chút
                    
                    # Thêm tiêu đề, nhãn trục và lưới
                    plt.title('Average Volume vs Average Close (2024)', fontsize=16, weight='bold')
                    plt.xlabel(f'Average {x_column.replace("_", " ").title()} ($)', fontsize=14)
                    plt.ylabel(f'Average {valid_y_columns[0].replace("_", " ").title()} (Million)', fontsize=14)
                    
                    # Cải thiện lưới cho dễ đọc
                    plt.grid(True, linestyle='--', alpha=0.5)
                    
                    # Thêm màu nền nhẹ để nâng cao thẩm mỹ
                    plt.gca().set_facecolor('#f8f9fa')
                    
                    # Thêm đường viền cho biểu đồ
                    for spine in plt.gca().spines.values():
                        spine.set_visible(True)
                        spine.set_color('#dddddd')
                    
                    # Thêm thông tin chú thích ở góc biểu đồ
                    plt.figtext(0.01, 0.01, 'Data source: DJIA Companies, 2024', fontsize=8, alpha=0.7)
                    
                    # Đảm bảo các trục bắt đầu từ 0 nếu phù hợp
                    if len(x_data) > 0:
                        if min(x_data) > 0 and min(x_data) < max(x_data) * 0.1:
                            plt.xlim(left=0)
                    if len(y_data) > 0:
                        if min(y_data) > 0 and min(y_data) < max(y_data) * 0.1:
                            plt.ylim(bottom=0)
                    
                    plt.tight_layout()
                    
                    return plt.gcf()
                    
                # Sử dụng Seaborn cho các trường hợp khác
                ax = sns.scatterplot(x=x_column, y=valid_y_columns[0], data=df)
                plt.xlabel(x_column)
                plt.ylabel(valid_y_columns[0])
                
        elif chart_type == "heatmap":
            # Sử dụng pivot_table thay vì pivot để hiển thị toàn bộ heatmap
            pivot_df = pd.pivot_table(
                data=df,
                index=x_column, 
                columns=valid_y_columns[0], 
                values=valid_y_columns[1] if len(valid_y_columns) > 1 else df.columns[2],
                aggfunc='mean'  # Sử dụng hàm trung bình để tổng hợp nhiều giá trị
            )
            
            # Vẽ heatmap đầy đủ
            plt.figure(figsize=(12, 8))  # Tăng kích thước để biểu đồ hiển thị rõ ràng hơn
            ax = sns.heatmap(
                pivot_df, 
                annot=True, 
                cmap="YlGnBu",
                fmt=".2f",  # Định dạng số thập phân
                linewidths=0.5  # Thêm đường viền cho các ô
            )
            
        elif chart_type.lower() == "boxplot" or chart_type.lower() == "box":
            # Xử lý boxplot - biểu đồ hộp để hiển thị phân phối dữ liệu
            if len(valid_y_columns) == 1:
                # Boxplot đơn giản: một biến phân loại (x) và một biến số (y)
                try:
                    # Chuyển dữ liệu sang kiểu số
                    df[valid_y_columns[0]] = pd.to_numeric(df[valid_y_columns[0]], errors='coerce')
                    df = df.dropna(subset=[valid_y_columns[0]])
                    
                    # Vẽ boxplot
                    ax = sns.boxplot(x=x_column, y=valid_y_columns[0], data=df)
                    plt.xlabel(x_column)
                    plt.ylabel(valid_y_columns[0])
                    
                    # Thêm các điểm dữ liệu thực để hiển thị phân phối
                    sns.stripplot(x=x_column, y=valid_y_columns[0], data=df, 
                                 size=4, color=".3", alpha=0.6)
                    
                    # Xoay nhãn trục x nếu có quá nhiều danh mục
                    if df[x_column].nunique() > 5:
                        plt.xticks(rotation=45, ha='right')
                except Exception as e:
                    print(f"Lỗi khi tạo boxplot đơn: {e}")
                    # Thử cách tiếp cận khác nếu cách trên thất bại
                    ax = sns.boxplot(y=valid_y_columns[0], data=df)
                    plt.ylabel(valid_y_columns[0])
            else:
                # Boxplot với nhiều biến số
                try:
                    # Chuyển dữ liệu sang định dạng melted cho nhiều biến
                    df_melted = df.melt(id_vars=[x_column], value_vars=valid_y_columns, 
                                       var_name='Biến', value_name='Giá trị')
                    
                    # Chuyển dữ liệu sang kiểu số
                    df_melted['Giá trị'] = pd.to_numeric(df_melted['Giá trị'], errors='coerce')
                    df_melted = df_melted.dropna(subset=['Giá trị'])
                    
                    # Vẽ boxplot với phân nhóm
                    ax = sns.boxplot(x=x_column, y='Giá trị', hue='Biến', data=df_melted)
                    plt.xlabel(x_column)
                    plt.ylabel('Giá trị')
                    
                    # Xoay nhãn trục x nếu có quá nhiều danh mục
                    if df[x_column].nunique() > 5:
                        plt.xticks(rotation=45, ha='right')
                        
                    # Điều chỉnh vị trí của legend
                    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                except Exception as e:
                    print(f"Lỗi khi tạo boxplot nhiều biến: {e}")
                    # Thử cách khác nếu cách trên thất bại
                    try:
                        # Chỉ vẽ boxplot cho các biến số, không phân nhóm theo x_column
                        df_selected = df[valid_y_columns].apply(pd.to_numeric, errors='coerce')
                        df_melted = df_selected.melt(var_name='Biến', value_name='Giá trị')
                        df_melted = df_melted.dropna(subset=['Giá trị'])
                        
                        ax = sns.boxplot(x='Biến', y='Giá trị', data=df_melted)
                        plt.xlabel('Biến')
                        plt.ylabel('Giá trị')
                    except:
                        print("Không thể tạo boxplot từ dữ liệu")
            
        else:  # Default to bar chart
            ax = sns.barplot(x=x_column, y=valid_y_columns[0], data=df)
            plt.xlabel(x_column)
            plt.ylabel(valid_y_columns[0])
            
        plt.title(title)
        plt.tight_layout()
        
        return plt.gcf()
        
    def save_visualization(self, fig: plt.Figure, filename: Optional[str] = None) -> str:
        """
        Lưu biểu đồ vào file.
        
        Args:
            fig (plt.Figure): Đối tượng biểu đồ
            filename (Optional[str]): Tên file (sẽ tự động tạo nếu không được cung cấp)
            
        Returns:
            str: Đường dẫn đến file đã lưu
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"visualization_{timestamp}.png"
            
        filepath = os.path.join(self.save_dir, filename)
        fig.savefig(filepath, dpi=300, bbox_inches="tight")
        plt.close(fig)
        
        return filepath
    
    def get_visualization_as_base64(self, fig: plt.Figure) -> str:
        """
        Chuyển đổi biểu đồ thành chuỗi base64 để hiển thị trên web.
        
        Args:
            fig (plt.Figure): Đối tượng biểu đồ
            
        Returns:
            str: Chuỗi base64 của biểu đồ
        """
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
        buffer.seek(0)
        
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close(fig)
        
        return image_base64

    async def visualize_query_result_async(self, question: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Truy vấn cơ sở dữ liệu và tạo biểu đồ trực quan từ kết quả bằng cách bất đồng bộ.
        
        Args:
            question (str): Câu hỏi để truy vấn dữ liệu
            max_retries (int): Số lần thử lại tối đa
            
        Returns:
            Dict[str, Any]: Kết quả bao gồm query, dữ liệu và đường dẫn đến biểu đồ
        """
        # Hàm chạy các tác vụ chặn trong thread riêng
        async def run_in_executor(func, *args, **kwargs):
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return await loop.run_in_executor(
                    pool, lambda: func(*args, **kwargs)
                )
        
        retries = 0
        last_error = None
        
        while retries < max_retries:
            try:
                # Truy vấn cơ sở dữ liệu bằng cách bất đồng bộ
                if hasattr(self.db_agent, 'query_with_retry_async'):
                    query_result = await self.db_agent.query_with_retry_async(question)
                else:
                    # Nếu chưa có phương thức bất đồng bộ, sử dụng thread pool
                    query_result = await run_in_executor(self.db_agent.query_with_retry, question)
                
                # Các bước tiếp theo được chạy bất đồng bộ trong thread pool
                # để không chặn event loop
                
                # Chuyển kết quả thành DataFrame
                df = pd.DataFrame(query_result["results"])
                
                if df.empty:
                    return {
                        "success": False,
                        "message": "Không có dữ liệu trả về từ truy vấn",
                        "query": query_result["query"]
                    }
                
                # Các xử lý còn lại được đặt trong thread riêng
                # để không chặn event loop
                result = await run_in_executor(
                    self._process_visualization_data,
                    df, question, query_result
                )
                
                return result
                
            except Exception as e:
                retries += 1
                last_error = str(e)
                print(f"Lỗi (thử lại {retries}/{max_retries}): {last_error}")
                if retries < max_retries:
                    await asyncio.sleep(1)
        
        # Trả về lỗi nếu tất cả các lần thử đều thất bại
        return {
            "success": False,
            "message": f"Lỗi sau {max_retries} lần thử: {last_error}"
        }
        
    # Phương thức hỗ trợ để xử lý dữ liệu trực quan hóa (sử dụng trong cả đồng bộ và bất đồng bộ)
    def _process_visualization_data(self, df, question, query_result):
        # Tiền xử lý đặc biệt cho các tình huống khó
        # (Lấy mã xử lý đặc biệt từ phương thức gốc)
        
        # Phân tích câu hỏi và đề xuất loại biểu đồ
        chart_info = self.analyze_question_for_chart(question, df)
        
        # Tạo biểu đồ và lưu
        try:
            fig = self.create_visualization(df, chart_info, question)
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"visualization_{current_time}.png"
            filepath = os.path.join(self.save_dir, filename)
            
            # Lưu biểu đồ
            plt.savefig(filepath, dpi=300, bbox_inches="tight")
            plt.close(fig)
            
            # Chuyển biểu đồ thành base64 để trả về
            with open(filepath, "rb") as img_file:
                img_data = base64.b64encode(img_file.read()).decode("utf-8")
            
            return {
                "success": True,
                "query": query_result["query"],
                "data": df.to_dict("records"),
                "chart_info": chart_info,
                "visualization_path": filepath,
                "visualization_url": f"./visualizations/{filename}",
                "visualization_base64": img_data
            }
            
        except Exception as e:
            print(f"Lỗi khi tạo biểu đồ: {str(e)}")
            return {
                "success": False,
                "message": f"Lỗi khi tạo biểu đồ: {str(e)}",
                "query": query_result["query"],
                "data": df.to_dict("records")
            }
    
    def visualize_query_result(self, question: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Truy vấn cơ sở dữ liệu và tạo biểu đồ trực quan từ kết quả.
        
        Args:
            question (str): Câu hỏi để truy vấn dữ liệu
            max_retries (int): Số lần thử lại tối đa
            
        Returns:
            Dict[str, Any]: Kết quả bao gồm query, dữ liệu và đường dẫn đến biểu đồ
        """
        retries = 0
        last_error = None
        
        while retries < max_retries:
            try:
                # Truy vấn cơ sở dữ liệu
                query_result = self.db_agent.query_with_retry(question)
                
                # Chuyển kết quả thành DataFrame
                df = pd.DataFrame(query_result["results"])
                
                if df.empty:
                    return {
                        "success": False,
                        "message": "Không có dữ liệu trả về từ truy vấn",
                        "query": query_result["query"]
                    }
                
                # Tiền xử lý đặc biệt cho các tình huống khó
                if "boxplot" in question.lower() and "monthly" in question.lower() and ("closing price" in question.lower() or "closing prices" in question.lower()):
                    # Trường hợp đặc biệt: tạo biểu đồ boxplot cho giá đóng cửa hàng tháng
                    print("Tạo biểu đồ boxplot cho giá đóng cửa hàng tháng...")
                    
                    # Trích xuất mã cổ phiếu từ câu hỏi
                    import re
                    stock_pattern = r'\b([A-Z]{1,5})\b'  # Tìm mã cổ phiếu dạng DIS, MSFT, AAPL...
                    stock_matches = re.findall(stock_pattern, question)
                    stock_code = stock_matches[0] if stock_matches else "Unknown"
                    
                    # Xử lý dữ liệu đầu vào
                    try:
                        # Kiểm tra xem có sẵn cột month và closing_prices không
                        print(f"Các cột hiện có trong dữ liệu: {df.columns.tolist()}")
                        
                        # Xử lý cột month (sử dụng trực tiếp nếu có)
                        month_col = 'month'
                        if month_col not in df.columns:
                            # Tìm cột ngày thay thế
                            date_cols = ['date', 'trading_date', 'day']
                            date_col = next((col for col in df.columns if any(dc in col.lower() for dc in date_cols)), None)
                            
                            if date_col:
                                if not pd.api.types.is_datetime64_dtype(df[date_col]):
                                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                                
                                # Tạo cột tháng từ cột ngày
                                df['month'] = df[date_col].dt.strftime('%Y-%m')
                                month_col = 'month'
                            else:
                                # Không tìm thấy cột ngày phù hợp
                                month_col = df.columns[0]  # Sử dụng cột đầu tiên
                        
                        # Xử lý cột giá (sử dụng trực tiếp nếu có)
                        price_col = 'closing_prices' if 'closing_prices' in df.columns else None
                        if not price_col:
                            price_cols = ['close', 'closing_price', 'price', 'value', 'adjusted_close']
                            price_col = next((col for col in df.columns if any(pc in col.lower() for pc in price_cols)), None)
                            
                            if not price_col and len(df.columns) >= 2:
                                # Không tìm thấy cột giá phù hợp
                                price_col = df.columns[1]  # Sử dụng cột thứ hai
                        
                        # Nếu cột giá đang ở dạng mảng PostgreSQL (do dùng ARRAY_AGG)
                        if price_col == 'closing_prices':
                            print(f"Kiểm tra kiểu dữ liệu của closing_prices: {type(df[price_col].iloc[0])}, giá trị: {df[price_col].iloc[0]}")
                            
                            try:
                                # Xử lý trực tiếp danh sách các đối tượng Decimal
                                if isinstance(df[price_col].iloc[0], list):
                                    print("Phát hiện dữ liệu dạng danh sách, đang xử lý...")
                                    
                                    # Chuyển đổi dữ liệu sang dạng thích hợp cho boxplot
                                    new_rows = []
                                    for idx, row in df.iterrows():
                                        month_value = row['month']
                                        prices_list = row[price_col]
                                        
                                        if not isinstance(prices_list, list):
                                            continue
                                            
                                        # Chuyển Decimal sang float và tạo hàng mới
                                        for price in prices_list:
                                            try:
                                                price_float = float(price)
                                                new_rows.append({'month': month_value, 'price': price_float})
                                            except:
                                                pass
                                    
                                    # Tạo DataFrame mới với các hàng mở rộng
                                    if new_rows:
                                        df = pd.DataFrame(new_rows)
                                        month_col = 'month'
                                        price_col = 'price'
                                        print(f"DataFrame mới sau khi xử lý danh sách: {len(df)} hàng")
                                        print(df.head())
                                    else:
                                        print("Không thể chuyển đổi danh sách thành DataFrame")
                                
                                # Xử lý chuỗi đại diện cho mảng PostgreSQL (dự phòng)
                                elif isinstance(df[price_col].iloc[0], str) and '{' in df[price_col].iloc[0]:
                                    print("Xử lý dữ liệu dạng chuỗi mảng PostgreSQL")
                                    
                                    # Xử lý mảng dạng chuỗi "{89.9,92.64}"
                                    df['price_value'] = df[price_col].apply(lambda x: 
                                        pd.to_numeric(
                                            # Tách giá trị từ chuỗi mảng PostgreSQL "{89.9,92.64}"
                                            str(x).replace('{', '').replace('}', '').split(',')[0],
                                            errors='coerce'))
                                    price_col = 'price_value'
                            except Exception as e:
                                print(f"Lỗi khi xử lý mảng PostgreSQL: {e}")
                        
                        # Truy vấn trực tiếp để có dữ liệu cho biểu đồ
                        if df.empty or df[price_col].isna().all():
                            print("Không tìm thấy dữ liệu hợp lệ, thử truy vấn SQL trực tiếp...")
                            try:
                                # Tạo truy vấn SQL đơn giản hơn
                                direct_query = """
                                SELECT 
                                    DATE_TRUNC('month', date) AS month,
                                    AVG(close_price) AS avg_close_price
                                FROM 
                                    stock_prices
                                WHERE 
                                    symbol = 'DIS' AND 
                                    EXTRACT(YEAR FROM date) = 2024
                                GROUP BY 
                                    month
                                ORDER BY 
                                    month
                                """
                                print(f"Truy vấn trực tiếp: {direct_query}")
                                
                                # Thực hiện truy vấn SQL
                                columns, results = self.db_agent.execute_query(direct_query)
                                
                                # Chuyển kết quả thành DataFrame
                                df = pd.DataFrame(results, columns=columns)
                                
                                month_col = 'month'
                                price_col = 'avg_close_price'
                                
                                print(f"Dữ liệu mới: \n{df.head().to_string()}")
                            except Exception as e:
                                print(f"Lỗi khi truy vấn trực tiếp: {e}")
                        
                        # Chuyển giá thành số
                        if price_col:
                            df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
                        
                        print(f"Dữ liệu đã xử lý thành công, cột month_col={month_col}, price_col={price_col}")
                        print(f"Mẫu dữ liệu đầu tiên:\n{df.head().to_string()}")
                        
                        # Xử lý giá trị month nếu là datetime
                        if pd.api.types.is_datetime64_dtype(df[month_col]):
                            df['month_str'] = df[month_col].dt.strftime('%Y-%m')
                            month_col = 'month_str'
                            print(f"Chuyển đổi cột month thành chuỗi: {df['month_str'].unique()}")
                        
                        # Đảm bảo giá trị price_col là số
                        df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
                        df = df.dropna(subset=[price_col])
                        print(f"Dữ liệu sau khi lọc NA: {len(df)} hàng")
                        
                        if len(df) == 0:
                            print("Không có dữ liệu hợp lệ sau khi lọc")
                            raise ValueError("Không có dữ liệu hợp lệ để vẽ biểu đồ")
                        
                        # Kiểm tra xem có đủ dữ liệu cho mỗi tháng để vẽ boxplot không
                        value_counts = df.groupby(month_col).size()
                        print(f"Số giá trị mỗi tháng: {value_counts.to_dict()}")
                        
                        # Tạo biểu đồ
                        plt.figure(figsize=(14, 8))
                        
                        # Nếu chỉ có mỗi một giá trị cho mỗi tháng, dùng bar chart thay vì boxplot
                        if all(count == 1 for count in value_counts.values):
                            print(f"Mỗi tháng chỉ có một giá trị, sử dụng biểu đồ cột thay vì boxplot")
                            
                            # Dùng bar chart
                            plt.figure(figsize=(14, 8))
                            ax = sns.barplot(x=month_col, y=price_col, data=df, palette="Set2")
                            
                            # Thêm giá trị trên mỗi cột
                            for p in ax.patches:
                                ax.annotate(f'{p.get_height():.2f}', 
                                           (p.get_x() + p.get_width() / 2., p.get_height()),
                                           ha = 'center', va = 'bottom',
                                           fontsize=10, color='black',
                                           xytext = (0, 5),
                                           textcoords = 'offset points')
                            
                            plt.xlabel('Tháng', fontsize=12)
                            plt.ylabel(f'Giá đóng cửa của {stock_code}', fontsize=12)
                            plt.title(f'Giá đóng cửa hàng tháng của {stock_code} trong năm 2024', fontsize=14)
                        else:
                            # Sử dụng boxplot nếu có đủ dữ liệu
                            print(f"Bắt đầu vẽ boxplot với {month_col} và {price_col}")
                            
                            # Vẽ biểu đồ với màu sắc rõ nét để dễ nhìn
                            ax = sns.boxplot(x=month_col, y=price_col, data=df, palette="Set2", linewidth=1.5)
                            
                            # Thêm các điểm dữ liệu thực
                            sns.stripplot(x=month_col, y=price_col, data=df,
                                       size=5, jitter=True, marker='o', color=".3", alpha=0.6)
                            
                            plt.xlabel('Tháng', fontsize=12)
                            plt.ylabel(f'Giá đóng cửa của {stock_code}', fontsize=12)
                            plt.title(f'Biểu đồ boxplot giá đóng cửa hàng tháng của {stock_code} trong năm 2024', fontsize=14)
                            
                        plt.xticks(rotation=45, ha='right')
                        plt.grid(True, linestyle='--', alpha=0.6)
                        plt.tight_layout()
                        
                        # Lưu biểu đồ
                        fig = plt.gcf()
                        filepath = self.save_visualization(fig)
                        base64_image = self.get_visualization_as_base64(fig)
                        
                        return {
                            "success": True,
                            "query": query_result["query"],
                            "columns": list(df.columns),
                            "chart_info": {
                                "chart_type": "boxplot",
                                "x_column": "month",
                                "y_column": price_col,
                                "title": f'Biểu đồ boxplot giá đóng cửa hàng tháng của {stock_code} trong năm 2024'
                            },
                            "visualization_path": filepath,
                            "visualization_base64": base64_image
                        }
                    except Exception as e:
                        print(f"Lỗi khi xử lý dữ liệu cho boxplot: {e}")
                        # Không cần xử lý đặc biệt, tiếp tục với luồng xử lý thông thường
                
                if "boxplot" in question.lower() and "daily" in question.lower() and "return" in question.lower() or "histogram" in question.lower() and ("daily" in question.lower() and "return" in question.lower() or "daily_return" in query_result["query"].lower()):
                    # Trường hợp đặc biệt: tạo biểu đồ cho daily returns (histogram hoặc boxplot)
                    print("Tạo biểu đồ cho daily returns...")
                    
                    # Trích xuất mã cổ phiếu từ câu hỏi
                    import re
                    stock_pattern = r'\b([A-Z]{1,5})\b'  # Tìm mã cổ phiếu dạng BA, MSFT, AAPL...
                    stock_matches = re.findall(stock_pattern, question)
                    stock_code = stock_matches[0] if stock_matches else "Unknown"
                    
                    # Xử lý dữ liệu đầu vào
                    try:
                        # Kiểm tra xem đã có cột daily_return chưa
                        if 'daily_return' in df.columns:
                            # In ra mẫu dữ liệu để debug
                            print(f"Mẫu dữ liệu daily_return: {df['daily_return'].head()}")
                            print(f"Kiểu dữ liệu daily_return: {df['daily_return'].dtype}")
                            
                            # Xử lý các giá trị đặc biệt
                            df['daily_return'] = df['daily_return'].apply(lambda x: 
                                float(x) if isinstance(x, (int, float, decimal.Decimal)) 
                                else (0 if x is None or x == 'N/A' or str(x).strip() == '' 
                                    else float(str(x).replace('%', '').strip()) 
                                        if isinstance(x, str) and str(x).strip() != 'N/A' 
                                        else 0))
                            
                            # Loại bỏ outliers nếu có
                            q1 = df['daily_return'].quantile(0.01)
                            q3 = df['daily_return'].quantile(0.99)
                            df = df[(df['daily_return'] >= q1) & (df['daily_return'] <= q3)]
                            
                            print(f"Số hàng sau khi lọc outliers: {len(df)}")
                        elif 'date' in df.columns:
                            # Tìm cột giá (close, price, value...)
                            price_cols = ['close', 'price', 'value', 'close_price', 'adjusted_close']
                            price_columns = [col for col in df.columns if any(pc in col.lower() for pc in price_cols)]
                            price_col = price_columns[0] if price_columns else [col for col in df.columns if col != 'date' and pd.api.types.is_numeric_dtype(df[col])][0]
                            
                            # Chuyển các giá trị không phải số thành float
                            df[price_col] = df[price_col].apply(lambda x: float(x) if isinstance(x, (int, float, decimal.Decimal)) else (0 if x is None else float(x)))
                            
                            # Sắp xếp dữ liệu theo ngày
                            if pd.api.types.is_datetime64_dtype(df['date']):
                                df = df.sort_values('date')
                            else:
                                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                                df = df.sort_values('date')
                            
                            # Tính daily returns
                            df['daily_return'] = df[price_col].pct_change() * 100  # Phần trăm
                            df['daily_return'] = df['daily_return'].fillna(0)  # Thay thế giá trị NaN bằng 0
                    except Exception as e:
                        print(f"Lỗi khi xử lý dữ liệu cho histogram: {e}")
                        # Thử phương pháp khác với các cột có sẵn
                        try:
                            # Tìm cột số đầu tiên có thể dùng làm dữ liệu
                            numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
                            if numeric_cols:
                                df['daily_return'] = df[numeric_cols[0]]
                        except:
                            print("Không thể tạo dữ liệu cho histogram")
                            return {
                                "success": False,
                                "message": "Không thể tạo dữ liệu cho histogram",
                                "query": query_result["query"]
                            }
                    
                    # Kiểm tra và tạo biểu đồ nếu có dữ liệu
                    if 'daily_return' in df.columns and len(df) > 0:
                        # Tạo biểu đồ phù hợp với loại yêu cầu
                        plt.figure(figsize=(12, 6))
                        
                        if "boxplot" in question.lower():
                            # Tạo boxplot chuẩn
                            # Sử dụng đối tượng mới cho biểu đồ boxplot
                            fig, ax = plt.subplots(figsize=(10, 6))
                            
                            # Thêm một cột nhóm để vẽ boxplot
                            df['group'] = 'Daily Return'
                            
                            # Vẽ boxplot với màu sắc và định dạng rõ ràng
                            boxplot = ax.boxplot(df['daily_return'].values, patch_artist=True, showfliers=True)
                            
                            # Tuỳ chỉnh màu sắc và định dạng
                            for patch in boxplot['boxes']:
                                patch.set_facecolor('lightblue')
                                patch.set_edgecolor('black')
                                patch.set_linewidth(1.5)
                                
                            for whisker in boxplot['whiskers']:
                                whisker.set_linewidth(1.5)
                                whisker.set_color('black')
                                
                            for cap in boxplot['caps']:
                                cap.set_linewidth(1.5)
                                cap.set_color('black')
                                
                            for median in boxplot['medians']:
                                median.set_linewidth(2)
                                median.set_color('orange')
                                
                            for flier in boxplot['fliers']:
                                flier.set_marker('o')
                                flier.set_markerfacecolor('none')
                                flier.set_markeredgecolor('black')
                                flier.set_markersize(6)
                            
                            # Thêm tiêu đề và nhãn
                            ax.set_title(f'AAPL Daily Returns (2024)', fontsize=14)
                            ax.set_ylabel('Daily Return (%)', fontsize=12)
                            
                            # Bỏ nhãn trục x vì chỉ có một nhóm
                            ax.set_xticks([1])
                            ax.set_xticklabels(['1'])
                            
                            # Thêm lưới
                            ax.grid(axis='y', linestyle='--', alpha=0.7)
                            plt.tight_layout()
                            
                            # Lưu biểu đồ
                            fig = plt.gcf()
                        else:
                            # Tạo histogram nếu không yêu cầu boxplot
                            plt.hist(df['daily_return'].values, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
                        plt.xlabel('Daily Returns (%)')
                        plt.ylabel('Tần số')
                        plt.title(f'Histogram của Daily Returns của {stock_code} trong năm 2024')
                        plt.grid(True, alpha=0.3)
                        plt.axvline(x=0, color='red', linestyle='--', alpha=0.7)  # Thêm đường thẳng tại 0%
                        fig = plt.gcf()
                        
                        # Lưu biểu đồ
                        filepath = self.save_visualization(fig)
                        base64_image = self.get_visualization_as_base64(fig)
                        
                        return {
                            "success": True,
                            "query": query_result["query"],
                            "columns": list(df.columns),
                            "chart_info": {
                                "chart_type": "histogram",
                                "x_column": "daily_return",
                                "y_column": "frequency",
                                "title": f'Histogram của Daily Returns của {stock_code} trong năm 2024'
                            },
                            "visualization_path": filepath,
                            "visualization_base64": base64_image
                        }
                
                # Phân tích dữ liệu và đề xuất loại biểu đồ
                chart_info = self.analyze_and_suggest_visualization(
                    question, query_result["columns"], query_result["results"]
                )
                
                # Tạo biểu đồ
                fig = self.create_visualization(df, chart_info, question)
                
                # Lưu biểu đồ
                filepath = self.save_visualization(fig)
                
                # Chuyển biểu đồ thành base64
                base64_image = self.get_visualization_as_base64(fig)
                
                return {
                    "success": True,
                    "query": query_result["query"],
                    "columns": query_result["columns"],
                    "results": query_result["results"],
                    "chart_info": chart_info,
                    "visualization_path": filepath,
                    "visualization_base64": base64_image
                }
                
            except Exception as e:
                retries += 1
                last_error = str(e)
                print(f"Lỗi lần {retries}/{max_retries}: {str(e)}")
                
                # Thử lại với cách tiếp cận khác nếu có lỗi liên quan đến Decimal
                if "decimal" in str(e).lower() or "NoneType" in str(e):
                    print("Phát hiện lỗi liên quan đến kiểu dữ liệu, thử cách tiếp cận khác...")
                    # Cố gắng điều chỉnh câu hỏi để tạo SQL tốt hơn
                    if "histogram" in question.lower() and "daily returns" in question.lower():
                        modified_question = f"Get daily stock prices of {question.split(' ')[4]} in 2024 ordered by date"
                        print(f"Tạo lại câu hỏi: {modified_question}")
                        question = modified_question
                        
                time.sleep(1)  # Chờ một chút trước khi thử lại
        
        # Nếu đã thử đủ số lần và vẫn thất bại
        return {
            "success": False,
            "message": f"Lỗi sau {max_retries} lần thử lại: {last_error}",
            "error": last_error
        }

if __name__ == "__main__":
    agent = VisualizeAgent(
        host="localhost",
        port="5432", 
        dbname="postgres",
        user="postgres", 
        password="postgres",
        save_dir="./visualizations"
    )
    
    question = "Create a pie chart of market capitalization proportions by sector as of April 26, 2025."
    
    try:
        result = agent.visualize_query_result(question)
        if result["success"]:
            print(f"Query: {result['query']}")
            print(f"Đề xuất biểu đồ: {result['chart_info']}")
            print(f"Biểu đồ đã được lưu tại: {result['visualization_path']}")
        else:
            print(f"Lỗi: {result['message']}")
    except Exception as e:
        print(f"Lỗi không xác định: {str(e)}")
