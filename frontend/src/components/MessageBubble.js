import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MessageBubble = ({ message, isUser, time, references, visualization, visualizationPath }) => {
  const messageClass = isUser ? 'user-message' : 'ai-message';

  // Format URL hiển thị thân thiện hơn
  const formatDisplayUrl = (url) => {
    try {
      if (!url) return "";
      
      // Kiểm tra URL có hợp lệ
      if (!url.startsWith('http')) return url;
      
      const cleanUrl = url.trim();
      // Trích xuất phần đường dẫn cuối cùng
      let displayText = cleanUrl.replace('https://tamanhhospital.vn/', '');
      
      // Xóa dấu / ở cuối nếu có
      if (displayText.endsWith('/')) {
        displayText = displayText.slice(0, -1);
      }
      
      // Thay thế dấu gạch ngang bằng khoảng trắng và viết hoa chữ cái đầu
      displayText = displayText
        .replace(/-/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
        
      return displayText;
    } catch (e) {
      console.error('Error formatting URL:', e);
      return url || "";
    }
  };

  // Để debug: hiển thị các tham chiếu nhận được
  console.log("References received:", references);

  // Loại bỏ các tham chiếu rỗng hoặc không hợp lệ
  const validReferences = references?.filter(ref => 
    ref && typeof ref === 'string' && ref.trim().startsWith('http')
  );

  return (
    <div className={`message-bubble ${messageClass}`}>
      <div className="message-text">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message}
        </ReactMarkdown>
        
        {/* Hiển thị biểu đồ nếu có */}
        {visualization && (
          <div className="visualization-container" style={{ marginTop: '15px', marginBottom: '15px', textAlign: 'center' }}>
            <img 
              src={`data:image/png;base64,${visualization}`} 
              alt="Biểu đồ phân tích" 
              style={{ maxWidth: '90%', width: '800px', borderRadius: '8px', border: '1px solid #e0e0e0', boxShadow: '0 2px 5px rgba(0,0,0,0.1)' }} 
            />
          </div>
        )}
        
        {/* Hiển thị biểu đồ từ đường dẫn file nếu có */}
        {visualizationPath && (
          <div className="visualization-container" style={{ marginTop: '15px', marginBottom: '15px', textAlign: 'center' }}>
            <img 
              src={`http://localhost:8080${visualizationPath}`} 
              alt="Biểu đồ phân tích" 
              style={{ maxWidth: '90%', width: '800px', borderRadius: '8px', border: '1px solid #e0e0e0', boxShadow: '0 2px 5px rgba(0,0,0,0.1)' }} 
            />
          </div>
        )}
        
        {validReferences && validReferences.length > 0 && (
          <div className="references-section">
            <h3>Tài liệu tham khảo:</h3>
            {validReferences.map((url, index) => (
              <div key={index} style={{
                display: 'block', 
                margin: '8px 0',
                lineHeight: '1.5',
                paddingLeft: '20px',
                position: 'relative'
              }}>
                <span style={{
                  position: 'absolute',
                  left: '5px',
                }}>•</span>
                <a 
                  href={url} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  style={{
                    color: isUser ? '#0077cc' : '#4db6ff',
                    textDecoration: 'none',
                    wordBreak: 'break-all',
                    display: 'inline-block',
                    width: '100%'
                  }}
                >
                  {formatDisplayUrl(url)}
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="message-time">{time}</div>
    </div>
  );
}

export default MessageBubble;
