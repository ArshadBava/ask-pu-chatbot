import React, { useState, useEffect, useRef, useCallback } from 'react';
// Restore original react-icons imports
import { FaGraduationCap, FaPaperPlane, FaUniversity, FaBookOpen, FaUsers, FaChalkboardTeacher, FaThumbsUp, FaThumbsDown, FaSyncAlt } from 'react-icons/fa';
// --- Add necessary icons for voice features ---
import { FaMicrophone, FaVolumeUp, FaVolumeMute } from 'react-icons/fa';
// Restore original CSS import
import './App.css';

// --- REMOVED AppStyles component ---

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(false);

  const chatWindowRef = useRef(null);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);

  // Use initial message with ID and timestamp
  const initialMessage = { id: Date.now(), text: "Hello! I am the Ask PU chatbot. How can I assist you today?", sender: 'bot', timestamp: new Date() };

  // --- Speech Synthesis (Text-to-Speech) ---
  const speak = useCallback((text) => {
    if (!speechEnabled || !('speechSynthesis' in window)) return;
    try {
        speechSynthesis.cancel(); // Cancel previous speech
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'en-US';
        speechSynthesis.speak(utterance);
    } catch (error) {
        console.error("Speech synthesis error:", error);
    }
  }, [speechEnabled]);

  // --- Effects ---
  useEffect(() => {
    setMessages([initialMessage]);
    if (inputRef.current) inputRef.current.focus();
  }, []);

  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  useEffect(() => {
    if (!isTyping && !isListening && inputRef.current) {
      setTimeout(() => inputRef.current.focus(), 100);
    }
  }, [isTyping, isListening]);

  // --- Speech Recognition (Speech-to-Text) Setup ---
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech Recognition not supported by this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => setIsListening(true);

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }
       setInput(finalTranscript || interimTranscript);
       if (finalTranscript) {
           stopListening(); // Stop when final result is clear
            // Optional: Automatically send after speech
           // handleSend(finalTranscript);
       }
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error, event.message);
      setIsListening(false);
       if (event.error === 'not-allowed') alert("Microphone permission denied. Please allow microphone access in browser settings.");
       else if (event.error !== 'no-speech' && event.error !== 'aborted') alert(`Speech error: ${event.error}`);
    };

    // onend is called when speech recognition stops (naturally or forced)
    recognition.onend = () => {
        setIsListening(false);
         // Refocus input if needed
         if (!isTyping && inputRef.current) {
             inputRef.current.focus();
         }
    };


    recognitionRef.current = recognition;

    // Cleanup function: abort recognition if component unmounts
    return () => recognitionRef.current?.abort();
  }, []); // Run setup once

  // --- Functions to control listening ---
  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      try {
        setInput(''); // Clear input before listening
        recognitionRef.current.start();
      } catch (error) { // Catch potential errors if start() is called improperly
        console.error("Error starting recognition:", error);
        setIsListening(false); // Reset state if start fails
      }
    }
  };

   // Use useCallback to potentially optimize if passed down as prop
   const stopListening = useCallback(() => {
     if (recognitionRef.current && isListening) {
        // Use abort() for immediate stop, stop() might have delay
       recognitionRef.current.abort();
       setIsListening(false); // Ensure state updates immediately
     }
   }, [isListening]); // Dependency on isListening state

   // Toggle listening state on mic click
   const handleMicClick = () => {
       if (isListening) {
           stopListening();
       } else {
           startListening();
       }
   };


  // --- Function to handle sending a message (Updated) ---
  const handleSend = async (messageText = input) => {
    const trimmedMessage = messageText.trim();
    if (!trimmedMessage) return;

    stopListening(); // Stop listening if sending

    const userMessage = { id: Date.now(), text: trimmedMessage, sender: 'user', timestamp: new Date() };
    const currentMessages = [...messages, userMessage];
    setMessages(currentMessages);
    setIsTyping(true);
    setInput('');

    const historyForBackend = currentMessages.slice(-5, -1).map(msg => ({ sender: msg.sender, text: msg.text }));

    try {
      // Ensure backend URL is correct
      const response = await fetch('http://127.0.0.1:8000/api/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmedMessage, history: historyForBackend }),
      });

      if (!response.ok) throw new Error(`Network error: ${response.status}`);

      const data = await response.json();
      const botMessage = { id: Date.now() + 1, text: data.response, sender: 'bot', timestamp: new Date() };
      setMessages(prevMessages => [...prevMessages, botMessage]);
      speak(data.response); // Speak the response

    } catch (error) {
      console.error("Error sending message:", error);
      const errorText = `Sorry, error: ${error.message}. Try again.`;
      const errorMessage = { id: Date.now() + 1, text: errorText, sender: 'bot', timestamp: new Date() };
      setMessages(prevMessages => [...prevMessages, errorMessage]);
      speak(errorText); // Speak error
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !isTyping && !isListening) handleSend();
  };

   const handleClearChat = () => {
      setMessages([initialMessage]);
      if ('speechSynthesis' in window) speechSynthesis.cancel();
      stopListening();
   }

   const handleFeedback = (messageId, feedbackType) => {
       console.log(`Feedback for message ${messageId}: ${feedbackType}`);
       setMessages(prevMessages => prevMessages.map(msg =>
           msg.id === messageId ? { ...msg, feedbackGiven: feedbackType } : msg
       ));
   };


  // Data for suggestion chips (using original icons)
  const suggestions = [
    { text: 'Admissions', icon: <FaUniversity /> },
    { text: 'Fee Structure', icon: <FaBookOpen /> },
    { text: 'about the campus', icon: <FaUsers /> },
    { text: 'university motto', icon: <FaChalkboardTeacher /> },
  ];

  return (
    <>
      {/* --- REMOVED AppStyles component --- */}
      <div className="mobile-frame">
        <div className="chat-container">
          <header className="chat-header">
            <div className="logo"><FaGraduationCap /></div>
            <div className="header-text-wrapper"> {/* Wrap text */}
                <h1>AskPU</h1>
                <p className="greeting">Your AI assistant for Pondicherry University</p>
            </div>
            <div className="header-buttons">
               <button onClick={() => setSpeechEnabled(prev => !prev)} className="icon-btn" title={speechEnabled ? "Disable Speech" : "Enable Speech"}>
                  {speechEnabled ? <FaVolumeUp /> : <FaVolumeMute />}
               </button>
               <button onClick={handleClearChat} className="icon-btn" title="Clear Chat">
                   <FaSyncAlt />
               </button>
            </div>
          </header>

          {isListening && <div className="listening-status">Listening... Speak now</div>}

          <main className="chat-log" ref={chatWindowRef}>
            {messages.map((msg, index) => (
              <div key={msg.id || index} className={`chat-message ${msg.sender}`}>
                  <div className="message-content-wrapper">
                    {msg.sender === 'bot' && <div className="avatar"><FaGraduationCap /></div>}
                    <div className="message-bubble">
                      <p>{msg.text}</p>
                      {msg.timestamp && <span className="timestamp">{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
                    </div>
                  </div>
                  {/* Feedback Buttons */}
                   {msg.sender === 'bot' && messages.length > 1 && !msg.feedbackGiven && (
                       <div className="feedback-actions">
                           <button onClick={() => handleFeedback(msg.id, 'like')} className="feedback-btn" title="Good"><FaThumbsUp /></button>
                           <button onClick={() => handleFeedback(msg.id, 'dislike')} className="feedback-btn" title="Bad"><FaThumbsDown /></button>
                       </div>
                   )}
                   {msg.feedbackGiven && <div className="feedback-given-indicator">Feedback: {msg.feedbackGiven === 'like' ? '👍' : '👎'}</div>}
              </div>
            ))}

            {isTyping && ( /* Typing indicator */
              <div className="chat-message bot">
                 <div className="message-content-wrapper">
                    <div className="avatar"><FaGraduationCap /></div>
                    <div className="message-bubble"><div className="typing-indicator"><span></span><span></span><span></span></div></div>
                 </div>
              </div>
            )}

            {messages.length <= 1 && !isTyping && !isListening && ( /* Suggestions */
                <div className="suggestions">
                  <p className="sub-heading">Suggested Questions</p>
                  <div className="suggestion-chips">
                    {suggestions.map((s, i) => ( <button key={i} onClick={() => handleSend(s.text)}>{s.icon} {s.text}</button> ))}
                  </div>
                </div>
            )}
          </main>

          <footer className="chat-input-area">
            <input
              ref={inputRef} type="text" value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={isListening ? "Listening..." : "Type or speak..."} // Changed placeholder
              disabled={isTyping || isListening}
            />
             {/* Microphone Button */}
            <button onClick={handleMicClick} className={`icon-btn mic-btn ${isListening ? 'listening' : ''}`} title={isListening ? "Stop" : "Speak"} disabled={isTyping} >
                <FaMicrophone style={{ color: isListening ? '#FF5733' : 'inherit' }} /> {/* Pass listening state via style */}
            </button>
             {/* Send Button */}
            <button className="icon-btn send-btn" onClick={() => handleSend()} disabled={!input.trim() || isTyping || isListening} >
              <FaPaperPlane />
            </button>
          </footer>
        </div>
      </div>
    </>
  );
}

export default App;

