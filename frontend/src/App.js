import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  // State for messages and user input
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false); // State to show bot is "typing"

  // Ref to automatically scroll to the latest message
  const chatWindowRef = useRef(null);

  // Add a welcome message when the component loads
  useEffect(() => {
    setMessages([
      { text: "Hello! I am the Ask PU chatbot. How can I help you today?", sender: 'bot' }
    ]);
  }, []);

  // Effect to scroll down when new messages are added
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages]);


  // Function to handle sending a message
  const handleSend = async () => {
    if (input.trim()) {
      const userMessage = { text: input, sender: 'user' };
      // Add user's message and show typing indicator
      setMessages(prevMessages => [...prevMessages, userMessage]);
      setIsTyping(true);
      setInput('');

      // --- API CALL TO THE BACKEND ---
      try {
        const response = await fetch('http://127.0.0.1:8000/api/chat/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: input }),
        });

        if (!response.ok) {
          throw new Error('Network response was not ok');
        }

        const data = await response.json();
        const botMessage = { text: data.response, sender: 'bot' };

        // Add the bot's response and hide typing indicator
        setMessages(prevMessages => [...prevMessages, botMessage]);

      } catch (error) {
        console.error("There was an error sending the message:", error);
        // Add an error message to the chat
        const errorMessage = { text: "Sorry, I'm having trouble connecting. Please try again later.", sender: 'bot' };
        setMessages(prevMessages => [...prevMessages, errorMessage]);
      } finally {
        setIsTyping(false);
      }
      // -----------------------------
    }
  };

  // Function to handle pressing Enter key
  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div className="App">
      <header className="header">
        <h1>Ask PU Chatbot</h1>
        <p>Your AI assistant for Pondicherry University</p>
      </header>
      <div className="chat-window" ref={chatWindowRef}>
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.sender}`}>
            <p>{msg.text}</p>
          </div>
        ))}
        {/* Show the typing indicator when the bot is "thinking" */}
        {isTyping && (
          <div className="message bot">
            <p><i>Typing...</i></p>
          </div>
        )}
      </div>
      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message..."
          disabled={isTyping} // Disable input while bot is typing
        />
        <button onClick={handleSend} disabled={isTyping}>Send</button>
      </div>
    </div>
  );
}

export default App;