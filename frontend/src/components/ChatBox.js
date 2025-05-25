import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import MessageInput from './MessageInput';
import AgentThinking from './AgentThinking';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChartLine } from '@fortawesome/free-solid-svg-icons';
import './ChatBox.css';

const ChatBox = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showIntro, setShowIntro] = useState(true);
  const [activeAgent, setActiveAgent] = useState('conversation');
  const [debugMode, setDebugMode] = useState(true); // Bật chế độ debug mặc định
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Hàm debug để log thông tin
  const logDebug = (...args) => {
    if (debugMode) {
      console.log(...args);
    }
  };
  
  // Theo dõi thay đổi của activeAgent
  useEffect(() => {
    logDebug('===== AGENT STATE CHANGE =====');
    logDebug('activeAgent đã thay đổi:', activeAgent);
    // Cập nhật title để theo dõi giá trị
    document.title = `Agent: ${activeAgent} - Financi`;
  }, [activeAgent]);

  // Hàm xác định agent đang hoạt động dựa trên thông tin từ backend
  const determineActiveAgent = (answer, routingInfo, hasVisualization) => {
    logDebug('Xác định agent từ:', { answer, routingInfo, hasVisualization });
    
    // Mặc định là conversation agent
    let agent = 'conversation';
    
    try {
      // Theo mã nguồn của backend, các agent sẽ chạy theo thứ tự:
      // router -> conversation -> database_query -> google_search -> visualize -> synthesizer
      
      // 1. Kiểm tra selected_agents trong routing_info (quan trọng nhất)
      if (routingInfo && routingInfo.selected_agents && routingInfo.selected_agents.length > 0) {
        logDebug('Các agent được chọn:', routingInfo.selected_agents);
        
        // Lấy agent có mức độ ưu tiên cao nhất trong selected_agents
        // Thứ tự ưu tiên: visualize > database_query > google_search > conversation
        
        // Nếu có visualize và có dữ liệu biểu đồ
        if (routingInfo.selected_agents.includes('visualize') && hasVisualization) {
          agent = 'visualize';
        }
        // Nếu có database_query 
        else if (routingInfo.selected_agents.includes('database_query')) {
          agent = 'database_query';
        }
        // Nếu có google_search
        else if (routingInfo.selected_agents.includes('google_search')) {
          agent = 'google_search';
        }
        // Nếu chỉ có conversation hoặc agent khác, lấy agent đầu tiên
        else {
          agent = routingInfo.selected_agents[0];
        }
      }
      
      // 2. Kiểm tra thông tin confidence của từng agent 
      else if (routingInfo && routingInfo.agents && Array.isArray(routingInfo.agents)) {
        // Lọc ra các agent được chọn (selected = true)
        const selectedAgents = routingInfo.agents
          .filter(a => a.selected)
          .map(a => a.name);
        
        logDebug('Các agent được chọn dựa trên confidence:', selectedAgents);
        
        if (selectedAgents.length > 0) {
          // Áp dụng thứ tự ưu tiên tương tự như trên
          if (selectedAgents.includes('visualize') && hasVisualization) {
            agent = 'visualize';
          } else if (selectedAgents.includes('database_query')) {
            agent = 'database_query';
          } else if (selectedAgents.includes('google_search')) {
            agent = 'google_search';
          } else {
            agent = selectedAgents[0];
          }
        }
      }
      
      // 3. Phân tích nội dung câu trả lời nếu vẫn chưa xác định được agent
      if (agent === 'conversation') {
        // Chuyển nội dung câu trả lời về chữ thường để tìm kiếm
        const lowerAnswer = (answer || '').toLowerCase();
        
        // Nếu có biểu đồ
        if (hasVisualization) {
          agent = 'visualize';
        }
        // Nếu có từ khóa liên quan đến database
        else if (lowerAnswer.includes('database') || lowerAnswer.includes('sql') || 
                 lowerAnswer.includes('query') || lowerAnswer.includes('dữ liệu') ||
                 lowerAnswer.includes('bảng') || lowerAnswer.includes('cổ phiếu')) {
          agent = 'database_query';
        }
        // Nếu có từ khóa liên quan đến tìm kiếm
        else if (lowerAnswer.includes('search') || lowerAnswer.includes('tìm kiếm') || 
                 lowerAnswer.includes('google') || lowerAnswer.includes('web') ||
                 lowerAnswer.includes('tin tức') || lowerAnswer.includes('mới nhất')) {
          agent = 'google_search';
        }
      }
    } catch (error) {
      console.error('Lỗi khi xác định agent:', error);
      // Nếu có lỗi, sử dụng conversation làm mặc định
      agent = 'conversation';
    }
    
    logDebug('Agent được xác định cuối cùng:', agent);
    return agent;
  };

  const handleSendMessage = async (message) => {
    if (showIntro) setShowIntro(false);
  
    const userMessage = { message, isUser: true, time: new Date().toLocaleTimeString() };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
  
    // Hiển thị trạng thái đang tải và đặt agent mặc định (conversation)
    setIsLoading(true);
    setActiveAgent('conversation'); // Reset agent về mặc định khi bắt đầu loading
    
    try {
      const response = await fetch('http://localhost:8080/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: message }),
      });
  
      if (!response.ok) {
        throw new Error(`Server error: ${response.statusText}`);
      }
  
      // Xử lý response từ API Financi-Agent
      const data = await response.json();
      
      // Lấy thông tin từ response
      const answer = data.answer;
      // eslint-disable-next-line no-unused-vars
      const routingInfo = data.routing_info;
      const visualizationBase64 = data.visualization_base64;
      
      // Tìm đường dẫn hình ảnh từ văn bản trả về
      let visualizationPath = null;
      // Biểu thức chính quy để tìm đường dẫn đến file visualization
      const visualizationRegex = /\.\/visualizations\/visualization_[\d_]+\.png/g;
      const visualizationMatch = answer.match(visualizationRegex);
      
      // eslint-disable-next-line no-useless-escape
      if (visualizationMatch && visualizationMatch.length > 0) {
        visualizationPath = visualizationMatch[0].replace('./', '/');
        console.log("Tìm thấy đường dẫn biểu đồ:", visualizationPath);
      }
      
      // Xác định agent đang được sử dụng (nếu có)
      logDebug('Dữ liệu trả về từ API:', data);
      
      // Tìm đường dẫn hình ảnh nếu chưa có
      const hasVisualization = visualizationBase64 || visualizationPath;
      
      // Biến để lưu giá trị agent được phát hiện
      let detectedAgent = "conversation"; // Mặc định
      
      // Ư u tiên sử dụng current_agent từ API nếu có
      if (data.current_agent) {
        // Log thông tin để debug
        logDebug('Sử dụng current_agent từ API:', data.current_agent);
        
        // Chuẩn hóa giá trị
        detectedAgent = data.current_agent.toString().toLowerCase().trim();
        
        // Log giá trị chuẩn hóa
        logDebug('Giá trị chuẩn hóa của agent:', detectedAgent);
      } else {
        // Nếu API không trả về current_agent, sử dụng hàm xác định của frontend
        detectedAgent = determineActiveAgent(answer, data.routing_info, hasVisualization);
        logDebug('Sử dụng agent được xác định từ frontend:', detectedAgent);
      }
      
      // Cập nhật state
      logDebug('Cập nhật activeAgent:', detectedAgent);
      setActiveAgent(detectedAgent);
      
      // Thêm URL tham khảo từ routing_info nếu có
      let references = [];
      
      // Đoạn này đã được di chuyển lên trên
      
      // Thêm tin nhắn vào danh sách
      setMessages((prevMessages) => {
        return [...prevMessages, {
          message: answer,
          isUser: false,
          time: new Date().toLocaleTimeString(),
          references: references.length > 0 ? Array.from(new Set(references)) : undefined,
          visualizationPath: visualizationPath,
          visualization: visualizationBase64
        }];
      });
      
      // Nếu có dữ liệu biểu đồ, xử lý hiển thị
      if (hasVisualization) {
        console.log("Có dữ liệu biểu đồ từ API");
      }
      
      // Lưu lại giá trị agent để tránh vấn đề closure
      const currentAgentValue = detectedAgent;
      
      // Trì hoãn tắt trạng thái loading để đảm bảo AgentThinking hiển thị đúng agent
      setTimeout(() => {
        console.log('Tắt trạng thái loading với agent:', currentAgentValue);
        
        // Đảm bảo agent được hiển thị đúng trước khi tắt loading
        if (currentAgentValue !== activeAgent) {
          console.log('Phát hiện sai lệch giữa agent khi tắt loading, cập nhật lại:', currentAgentValue);
          setActiveAgent(currentAgentValue);
          
          // Trì hoãn thêm để đảm bảo React cập nhật UI
          setTimeout(() => setIsLoading(false), 200);
        } else {
          setIsLoading(false);
        }
      }, 800);
    } catch (error) {
      const errorMessage = { message: `Error: ${error.message}`, isUser: false, time: new Date().toLocaleTimeString() };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
      // Giữ trạng thái loading thêm 500ms để đảm bảo AgentThinking hiển thị đúng agent
      // Chỉ đặt trạng thái loading về false sau khi các giá trị khác đã được cập nhật
      setTimeout(() => {
        setIsLoading(false);
      }, 500);
    }
  };
  
  return (
    <div className="chat-box">
      {showIntro && (
        <div className="deepseek-intro">
          <div className="icon-container">
            <FontAwesomeIcon icon={faChartLine} />
          </div>
          <div className="intro-text">
            <div className="greeting">Xin chào, tôi là Financi-Agent.</div>
            <div className="question">Bạn cần hỗ trợ gì về tài chính hôm nay?</div>
          </div>
        </div>
      )}

      <div className="messages">
        {messages.map((msg, index) => (
          <MessageBubble 
            key={index} 
            message={msg.message} 
            isUser={msg.isUser} 
            time={msg.time} 
            references={msg.references}
            visualization={msg.visualization}
            visualizationPath={msg.visualizationPath}
          />
        ))}
        {isLoading && <AgentThinking agentType={activeAgent} />}
        <div ref={messagesEndRef} />
      </div>
      <MessageInput onSendMessage={handleSendMessage} />
    </div>
  );
};

export default ChatBox;
