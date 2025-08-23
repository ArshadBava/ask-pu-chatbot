// -----------------------------------------------------------------
// FILE: frontend/src/App.js
// Replace the entire content of your App.js with this updated code.
// -----------------------------------------------------------------
import React, { useState, useEffect, useRef } from 'react';
import { FaGraduationCap, FaPaperPlane, FaUniversity, FaBookOpen, FaUsers, FaChalkboardTeacher } from 'react-icons/fa';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const chatWindowRef = useRef(null);
  const inputRef = useRef(null);

  // Add a welcome message and focus input on initial load
  useEffect(() => {
    setMessages([
      { text: "Hello! I am the Ask PU chatbot. How can I assist you today?", sender: 'bot' }
    ]);
    inputRef.current.focus();
  }, []);

  // Effect to scroll down when new messages are added
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  // --- NEW: A dedicated effect to handle refocusing the input ---
  // This is a more reliable method.
  useEffect(() => {
    // This effect runs whenever 'isTyping' changes.
    // We only want to focus when the bot has FINISHED typing.
    if (!isTyping) {
      // Use a timeout to ensure the DOM has updated and the input is no longer disabled
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 0);
    }
  }, [isTyping]);


  // Function to handle sending a message
  const handleSend = async (messageText = input) => {
    if (!messageText.trim()) return;

    const userMessage = { text: messageText, sender: 'user' };
    setMessages(prevMessages => [...prevMessages, userMessage]);
    setIsTyping(true);
    setInput('');

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText }),
      });

      if (!response.ok) throw new Error('Network response was not ok');

      const data = await response.json();
      const botMessage = { text: data.response, sender: 'bot' };
      setMessages(prevMessages => [...prevMessages, botMessage]);

    } catch (error) {
      console.error("There was an error sending the message:", error);
      const errorMessage = { text: "Sorry, I'm having trouble connecting. Please try again later.", sender: 'bot' };
      setMessages(prevMessages => [...prevMessages, errorMessage]);
    } finally {
      setIsTyping(false);
      // The focus logic has been moved to the new useEffect hook above
    }
  };

  // Function to handle pressing Enter key
  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      handleSend();
    }
  };

  // Data for suggestion chips
  const suggestions = [
    { text: 'Admissions', icon: <FaUniversity /> },
    { text: 'Fee Structure', icon: <FaBookOpen /> },
    { text: 'Student Services', icon: <FaUsers /> },
    { text: 'Faculty Directory', icon: <FaChalkboardTeacher /> },
  ];

  return (
    <div className="mobile-frame">
      <div className="chat-container">
        <header className="chat-header">
          <div className="logo">
            <FaGraduationCap />
          </div>
          <h1>AskPU</h1>
          <p className="greeting">Your AI assistant for Pondicherry University</p>
        </header>

        <main className="chat-log" ref={chatWindowRef}>
          {messages.map((msg, index) => (
            <div key={index} className={`chat-message ${msg.sender}`}>
              {msg.sender === 'bot' && (
                <div className="avatar">
                  <FaGraduationCap />
                </div>
              )}
              <div className="message-bubble">
                <p>{msg.text}</p>
              </div>
            </div>
          ))}

          {isTyping && (
            <div className="chat-message bot">
              <div className="avatar">
                <FaGraduationCap />
              </div>
              <div className="message-bubble">
                <div className="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          )}

          {messages.length <= 1 && (
             <div className="suggestions">
                <p className="sub-heading">Suggested Common Questions</p>
                <div className="suggestion-chips">
                  {suggestions.map((s, i) => (
                    <button key={i} onClick={() => handleSend(s.text)}>
                      {s.icon} {s.text}
                    </button>
                  ))}
                </div>
              </div>
          )}
        </main>

        <footer className="chat-input-area">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your question..."
            disabled={isTyping}
          />
          <button className="icon-btn send-btn" onClick={() => handleSend()} disabled={!input.trim() || isTyping}>
            <FaPaperPlane />
          </button>
        </footer>
      </div>
    </div>
  );
}

export default App;
