// App.js
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  FaGraduationCap, FaPaperPlane, FaUniversity, FaBookOpen,
  FaUsers, FaChalkboardTeacher, FaThumbsUp, FaThumbsDown, FaSyncAlt,
  FaMicrophone, FaVolumeUp, FaVolumeMute
} from 'react-icons/fa';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState(null);
  const [selectedLang, setSelectedLang] = useState('en-IN'); // default language for recognition & TTS

  // NEW: suggestions state (initial static fallback)
  const [suggestions, setSuggestions] = useState([
    { text: 'Admissions', icon: <FaUniversity /> },
    { text: 'Fee Structure', icon: <FaBookOpen /> },
    { text: 'about the campus', icon: <FaUsers /> },
    { text: 'university motto', icon: <FaChalkboardTeacher /> },
  ]);

  const chatWindowRef = useRef(null);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);
  const isListeningRef = useRef(false);
  const messagesRef = useRef([]);

  // initial message
  const initialMessage = { id: `init-${Date.now()}`, text: "Hello! I am the Ask PU chatbot. How can I assist you today?", sender: 'bot', timestamp: new Date() };

  useEffect(() => { messagesRef.current = messages; }, [messages]);

  // TTS speak
  const speak = useCallback((text) => {
    if (!speechEnabled || !('speechSynthesis' in window)) return;
    try {
      speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = selectedLang;
      const voices = speechSynthesis.getVoices();
      if (voices && voices.length) {
        const match = voices.find(v => v.lang && v.lang.toLowerCase().startsWith(selectedLang.split('-')[0]));
        if (match) utterance.voice = match;
      } else {
        window.speechSynthesis.onvoiceschanged = () => {
          const updated = window.speechSynthesis.getVoices();
          const match2 = updated.find(v => v.lang && v.lang.toLowerCase().startsWith(selectedLang.split('-')[0]));
          if (match2) utterance.voice = match2;
        };
      }
      speechSynthesis.speak(utterance);
    } catch (error) {
      console.error("Speech synthesis error:", error);
    }
  }, [speechEnabled, selectedLang]);

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

  useEffect(() => {
    if (recognitionRef.current) {
      try { recognitionRef.current.lang = selectedLang; } catch (e) { /* ignore */ }
    }
  }, [selectedLang]);

  // SpeechRecognition setup
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech Recognition not supported by this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = selectedLang;

    recognition.onstart = () => { setIsListening(true); isListeningRef.current = true; };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
        else interimTranscript += event.results[i][0].transcript;
      }
      setInput(finalTranscript || interimTranscript);
      if (finalTranscript) stopListening();
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error, event.message || '');
      setIsListening(false);
      isListeningRef.current = false;
      if (event.error === 'not-allowed') {
        alert("Microphone permission denied. Please allow microphone access in browser settings.");
      } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
        alert(`Speech error: ${event.error}`);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
      isListeningRef.current = false;
      if (!isTyping && inputRef.current) inputRef.current.focus();
    };

    recognitionRef.current = recognition;
    return () => { recognitionRef.current?.abort(); recognitionRef.current = null; };
  }, []);

  const startListening = () => {
    if (!recognitionRef.current) return console.warn("Recognition object not available.");
    try {
      recognitionRef.current.lang = selectedLang;
      setInput('');
      recognitionRef.current.start();
      setIsListening(true);
      isListeningRef.current = true;
    } catch (error) {
      console.error("Error starting recognition:", error);
      setIsListening(false);
      isListeningRef.current = false;
    }
  };

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListeningRef.current) {
      recognitionRef.current.abort();
      setIsListening(false);
      isListeningRef.current = false;
    } else {
      try { recognitionRef.current?.abort(); } catch(e) { /* ignore */ }
      setIsListening(false);
      isListeningRef.current = false;
    }
  }, []);

  const handleMicClick = () => {
    if (isListeningRef.current) stopListening();
    else startListening();
  };

  const genId = () => {
    if (typeof window?.crypto?.randomUUID === 'function') return window.crypto.randomUUID();
    return `${Date.now()}-${Math.floor(Math.random()*100000)}`;
  };

  const handleCopyMessage = async (text, messageId) => {
    if (!text) return;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const txtArea = document.createElement('textarea');
        txtArea.value = text;
        txtArea.style.position = 'fixed';
        txtArea.style.left = '-9999px';
        document.body.appendChild(txtArea);
        txtArea.select();
        document.execCommand('copy');
        document.body.removeChild(txtArea);
      }
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(prev => (prev === messageId ? null : prev)), 1800);
    } catch (err) {
      console.error("Copy failed:", err);
      alert("Unable to copy to clipboard.");
    }
  };

  // --- handleSend now updates suggestions state from backend response ---
  const handleSend = async (messageText = input) => {
    const trimmedMessage = messageText.trim();
    if (!trimmedMessage) return;

    stopListening();

    const userMessage = { id: genId(), text: trimmedMessage, sender: 'user', timestamp: new Date() };
    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);
    setInput('');

    const historyForBackend = messagesRef.current.slice(-5).map(m => ({ sender: m.sender, text: m.text }));

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmedMessage, history: historyForBackend }),
      });

      if (!response.ok) throw new Error(`Network error: ${response.status}`);
      let data;
      try { data = await response.json(); } catch (err) { throw new Error('Invalid JSON response from server'); }

      const botMessage = { id: genId(), text: data.response, sender: 'bot', timestamp: new Date() };
      setMessages(prev => [...prev, botMessage]);

      // NEW: update suggestions from backend (if provided). Keep up to 3.
      if (Array.isArray(data.suggestions) && data.suggestions.length) {
        // convert simple strings into { text, icon?: ... } if needed
        const normalized = data.suggestions.slice(0, 3).map(s => (typeof s === 'string' ? { text: s } : s));
        setSuggestions(normalized);
      } else {
        // if backend returned nothing, optionally keep existing suggestions or reset to default
        // setSuggestions([]); // <-- uncomment if you want to clear when none returned
      }

      speak(data.response);
    } catch (error) {
      console.error("Error sending message:", error);
      const errorText = `Sorry, error: ${error.message}. Try again.`;
      const errorMessage = { id: genId(), text: errorText, sender: 'bot', timestamp: new Date() };
      setMessages(prev => [...prev, errorMessage]);
      speak(errorText);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !isTyping && !isListening) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    setMessages([initialMessage]);
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    stopListening();
  };

  const handleFeedback = (messageId, feedbackType) => {
    setMessages(prevMessages => prevMessages.map(msg =>
      msg.id === messageId ? { ...msg, feedbackGiven: feedbackType } : msg
    ));
  };

  const langOptions = [
    { label: 'English (India)', code: 'en-IN' },
    { label: 'Hindi (हिन्दी)', code: 'hi-IN' },
    { label: 'Malayalam (മലയാളം)', code: 'ml-IN' },
  ];

  return (
    <>
      <div className="mobile-frame">
        <div className="chat-container">
          <header className="chat-header">
            <div className="header-left">
              <div className="logo"><FaGraduationCap /></div>
              <div className="header-text-wrapper">
                <h1 className="app-title">AskPU</h1>
                <p className="greeting">Your AI assistant for Pondicherry University</p>
              </div>
            </div>

            <div className="header-controls" role="group" aria-label="Chat controls">
              <div className="control control-lang">
                <button
                  className="icon-btn control-btn globe-btn"
                  title="Change language"
                  aria-label="Change recognition language"
                  onClick={() => document.getElementById('lang-select').showPicker?.()}
                >
                  🌐
                </button>
                <select
                  id="lang-select"
                  value={selectedLang}
                  onChange={(e) => setSelectedLang(e.target.value)}
                  aria-label="Select recognition language"
                  className="lang-select-hidden"
                >
                  {langOptions.map(opt => (
                    <option key={opt.code} value={opt.code}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={() => setSpeechEnabled(prev => !prev)}
                className="icon-btn control-btn"
                title={speechEnabled ? 'Disable Speech' : 'Enable Speech'}
                aria-label={speechEnabled ? 'Disable speech' : 'Enable speech'}
              >
                {speechEnabled ? <FaVolumeUp /> : <FaVolumeMute />}
              </button>

              <button
                onClick={handleClearChat}
                className="icon-btn control-btn"
                title="Clear Chat"
                aria-label="Clear chat"
              >
                <FaSyncAlt />
              </button>
            </div>
          </header>

          {isListening && <div className="listening-status">Listening... Speak now ({langOptions.find(l=>l.code===selectedLang)?.label})</div>}

          <main className="chat-log" ref={chatWindowRef} role="log" aria-live="polite">
            {messages.map((msg, index) => (
              <div key={msg.id || index} className={`chat-message ${msg.sender}`}>
                <div className="message-content-wrapper">
                  {msg.sender === 'bot' && <div className="avatar"><FaGraduationCap /></div>}
                  <div className="message-bubble">
                    <p>{msg.text}</p>
                    {msg.timestamp && <span className="timestamp">{msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
                  </div>
                </div>

                {msg.sender === 'bot' && messages.length > 1 && !msg.feedbackGiven && (
                  <div className="feedback-actions">
                    <button onClick={() => handleFeedback(msg.id, 'like')} className="feedback-btn" title="Good" aria-label="Mark helpful"><FaThumbsUp /></button>
                    <button onClick={() => handleFeedback(msg.id, 'dislike')} className="feedback-btn" title="Bad" aria-label="Mark not helpful"><FaThumbsDown /></button>
                    <button className="feedback-btn copy-btn" onClick={() => handleCopyMessage(msg.text, msg.id)} title="Copy reply" aria-label="Copy reply to clipboard">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                        <path d="M9 9H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <rect x="9" y="3" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                  </div>
                )}
                {msg.feedbackGiven && <div className="feedback-given-indicator">Feedback: {msg.feedbackGiven === 'like' ? '👍' : '👎'}</div>}
                {copiedMessageId === msg.id && <div className="copied-indicator" aria-live="polite">Copied!</div>}
              </div>
            ))}

            {isTyping && (
              <div className="chat-message bot">
                <div className="message-content-wrapper">
                  <div className="avatar"><FaGraduationCap /></div>
                  <div className="message-bubble"><div className="typing-indicator"><span></span><span></span><span></span></div></div>
                </div>
              </div>
            )}

            {/* Suggestions area: show dynamic suggestions (from backend) or fallback static */}
            {!isTyping && !isListening && suggestions && suggestions.length > 0 && (
              <div className="suggestions">
                <p className="sub-heading">Suggested Questions</p>
                <div className="suggestion-chips">
                  {suggestions.slice(0, 6).map((s, i) => (
                    <button key={i} onClick={() => handleSend(s.text || s)} aria-label={`Suggestion: ${s.text || s}`}>
                      {s.icon ? s.icon : <FaGraduationCap />} {s.text || s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </main>

          <footer className="chat-input-area">
            <input
              ref={inputRef} type="text" value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isListening ? "Listening..." : "Type or speak..."}
              disabled={isTyping || isListening}
              aria-label="Message input"
            />
            <button onClick={handleMicClick} className={`icon-btn mic-btn ${isListening ? 'listening' : ''}`} title={isListening ? "Stop" : "Speak"} disabled={isTyping} aria-label={isListening ? "Stop listening" : "Start speaking"}>
              <FaMicrophone style={{ color: isListening ? '#FF5733' : 'inherit' }} />
            </button>
            <button className="icon-btn send-btn" onClick={() => handleSend()} disabled={!input.trim() || isTyping || isListening} aria-label="Send message">
              <FaPaperPlane />
            </button>
          </footer>
        </div>
      </div>
    </>
  );
}

export default App;