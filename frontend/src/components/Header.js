import React, { useState } from 'react';
import { FaCommentDots } from "react-icons/fa";
import { BsClockHistory } from "react-icons/bs";
import './Header.css';

const Header = () => {
  // eslint-disable-next-line no-unused-vars
  const [isOpen, setIsOpen] = useState(false);

  const toggleChat = () => {
    setIsOpen(prev => !prev);
  };

  return (
    <div className="header">
      {/* Icon for the chat */}
      <button className="chat-icon" onClick={toggleChat}>
        <FaCommentDots />
      </button>

      {/* Chat title */}
      <div>Temporary Chat</div>

      {/* Chat state toggle */}
      <button className="chat-state" onClick={toggleChat}>
        <BsClockHistory />
      </button>
    </div>
  );
};

export default Header;
