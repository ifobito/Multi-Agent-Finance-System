import React, { useEffect } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChartLine, faDatabase, faSearch, faChartBar } from '@fortawesome/free-solid-svg-icons';
import './AgentThinking.css';

/**
 * Hiển thị trạng thái đang xử lý của agent đang được sử dụng
 * 
 * @param {string} agentType - Loại agent đang được sử dụng (conversation, database_query, google_search, visualize)
 * @returns Một component hiển thị icon và thông tin agent
 */
const AgentThinking = (props) => {
  // Đảm bảo rằng agentType có giá trị
  const agentType = props.agentType || 'conversation';
  console.log('PROPERTY PASSED:', props);
  // Debug: Hiển thị loại agent hiện tại trong console
  useEffect(() => {
    console.log('========== AGENT THINKING DEBUG ==========');
    console.log('agentType được truyền vào:', JSON.stringify(agentType));
    console.log('Kiểu dữ liệu của agentType:', typeof agentType);
    console.log('Giá trị agentType sau khi normalize:', agentType?.toLowerCase()?.trim());
    // Thử hiển thị trực tiếp trên giao diện
    document.title = `Agent: ${agentType} - Financi`;
  }, [agentType]);

  // Xác định icon và tên dựa vào loại agent
  const getAgentInfo = (type) => {
    console.log('===== DEBUG AGENT THINKING =====');
    console.log('Loại agent được truyền vào:', type);
    console.log('Kiểu dữ liệu:', typeof type);
    
    // Đảm bảo giá trị có định dạng hợp lệ
    let normalizedType = '';
    
    if (type) {
      try {
        normalizedType = type.toString().toLowerCase().trim();
      } catch (e) {
        console.error('Lỗi khi chuẩn hóa agent type:', e);
        normalizedType = 'conversation'; // Mặc định nếu có lỗi
      }
    }
    
    console.log('Giá trị sau khi normalize:', normalizedType);
    console.log('Bắt đầu so sánh để xác định agent:');
    
    // Kiểm tra rõ ràng từng trường hợp
    console.log('Thử kết hợp database:', normalizedType.includes('database'));
    console.log('Thử kết hợp search:', normalizedType.includes('search'));
    console.log('Thử kết hợp visual:', normalizedType.includes('visual'));
    
    // Xử lý theo case cụ thể trước
    if (normalizedType === 'visualize' || normalizedType === 'visualization' || normalizedType.includes('visual')) {
      console.log('==> VISUALIZATION AGENT');
      return { 
        icon: faChartBar, 
        name: 'Visualization Agent',
        description: 'Agent đang tạo biểu đồ trực quan hóa' 
      };
    } 
    else if (normalizedType === 'database_query' || normalizedType.includes('database') || normalizedType === 'db') {
      console.log('==> DATABASE AGENT');
      return { 
        icon: faDatabase, 
        name: 'Database Agent',
        description: 'Agent đang truy vấn cơ sở dữ liệu tài chính'
      };
    } 
    else if (normalizedType === 'google_search' || normalizedType.includes('search') || normalizedType.includes('google')) {
      console.log('==> SEARCH AGENT');
      return { 
        icon: faSearch, 
        name: 'Search Agent',
        description: 'Agent đang tìm kiếm thông tin mới nhất' 
      };
    } 
    else {
      console.log('==> DEFAULT TO CONVERSATION AGENT');
      return { 
        icon: faChartLine, 
        name: 'Financi Agent',
        description: 'Agent đang xử lý câu hỏi của bạn' 
      };
    }
  };

  // Lấy thông tin agent và ghi rõ hơn về quá trình
  console.log('Lấy thông tin cho agent:', agentType);
  const agentInfo = getAgentInfo(agentType);
  console.log('Kết quả getAgentInfo:', agentInfo);
  const { icon, name } = agentInfo;

  return (
    <div className="agent-thinking-container">
      <div className="agent-thinking">
        <div className="agent-icon">
          <FontAwesomeIcon icon={icon} />
        </div>
        <div className="thinking-content">
          <div className="thinking-name">{name}</div>
          <div className="thinking-text">
            đang xử lý<span className="dots"></span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentThinking;
