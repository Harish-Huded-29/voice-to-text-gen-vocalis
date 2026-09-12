import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const WS_URL = `ws://${window.location.hostname}:8000/ws`;

export default function App() {
  const [transcripts, setTranscripts] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [vadState, setVadState] = useState('listening'); // 'listening', 'speaking', 'transcribing', 'paused'
  const [isCapturing, setIsCapturing] = useState(true);
  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [micLevel, setMicLevel] = useState(0);

  const transcriptEndRef = useRef(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const isCapturingRef = useRef(isCapturing);

  useEffect(() => {
    isCapturingRef.current = isCapturing;
  }, [isCapturing]);

  // Connect to WebSocket
  useEffect(() => {
    let isMounted = true;

    function connect() {
      if (!isMounted) return;
      setConnectionStatus('connecting');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        setConnectionStatus('connected');
        // Synchronize capture state
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'set_capture', active: isCapturingRef.current }));
        }
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'status') {
            if (data.state) {
              setVadState(data.state);
            }
          } else if (data.type === 'volume') {
            if (isCapturingRef.current) {
              setMicLevel(data.level || 0);
            }
          } else if (data.type === 'transcript') {
            setTranscripts((prev) => [...prev, data]);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onclose = () => {
        if (!isMounted) return;
        setConnectionStatus('disconnected');
        setVadState('disconnected');
        reconnectTimeoutRef.current = setTimeout(connect, 1500);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const sendWsMessage = (msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  };

  // Only the USER manually toggles the mic ON or OFF
  const handleToggleCapture = () => {
    const nextState = !isCapturing;
    setIsCapturing(nextState);
    setVadState(nextState ? 'listening' : 'paused');
    if (!nextState) {
      setMicLevel(0);
    }
    sendWsMessage({ type: 'set_capture', active: nextState });
  };

  useEffect(() => {
    if (transcriptEndRef.current) {
      transcriptEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [transcripts]);

  const handleCopyAll = async () => {
    const fullText = transcripts.map((t) => t.text).join('\n');
    if (!fullText) return;
    try {
      await navigator.clipboard.writeText(fullText);
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  const handleCopySingle = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch (err) {
      console.error('Failed to copy sentence:', err);
    }
  };

  const handleClear = () => {
    setTranscripts([]);
  };

  // Status message computation
  const getStatusDisplay = () => {
    if (!isCapturing) {
      return {
        text: 'Microphone is OFF • Click below to start listening',
        stateClass: 'status-paused',
        dotColor: '#ef4444'
      };
    }
    if (connectionStatus !== 'connected') {
      return {
        text: 'Connecting to neural engine...',
        stateClass: 'status-connecting',
        dotColor: '#f59e0b'
      };
    }
    if (vadState === 'transcribing') {
      return {
        text: '⚡ Translating to English...',
        stateClass: 'status-transcribing',
        dotColor: '#8b5cf6'
      };
    }
    if (vadState === 'speaking' || micLevel > 12) {
      return {
        text: '🎤 Voice detected — Listening...',
        stateClass: 'status-speaking',
        dotColor: '#f59e0b'
      };
    }
    return {
      text: '🟢 Listening live • Speak in any language',
      stateClass: 'status-listening',
      dotColor: '#10b981'
    };
  };

  const currentStatus = getStatusDisplay();

  return (
    <div className="app-layout">
      {/* Top Header */}
      <header className="navbar">
        <div className="nav-brand">
          <div className="brand-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" x2="12" y1="19" y2="22"/>
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-title">Vocalis</span>
            <span className="brand-subtitle">Multilingual Neural Translator</span>
          </div>
        </div>

        <div className="nav-actions">
          <button
            className="btn-nav-icon"
            onClick={handleCopyAll}
            disabled={transcripts.length === 0}
            title="Copy all English text"
          >
            {copiedAll ? (
              <span className="copied-tag">Copied!</span>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
              </svg>
            )}
          </button>

          <button
            className="btn-nav-icon"
            onClick={handleClear}
            disabled={transcripts.length === 0}
            title="Clear transcripts"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18"/>
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
            </svg>
          </button>

          <div className={`connection-pill ${connectionStatus}`}>
            <span className="connection-dot"></span>
            <span className="connection-text">
              {connectionStatus === 'connected' ? 'Live' : connectionStatus === 'connecting' ? 'Connecting' : 'Offline'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Transcript Stream / Minimalist Hero */}
      <main className="content-board">
        {transcripts.length === 0 ? (
          <div className="empty-placeholder">
            <div className="minimal-waves">
              <span className="wave-line w-1"></span>
              <span className="wave-line w-2"></span>
              <span className="wave-line w-3"></span>
              <span className="wave-line w-4"></span>
              <span className="wave-line w-5"></span>
            </div>
            <h2 className="placeholder-heading">Speak in Any Language</h2>
            <p className="placeholder-subtext">
              Kannada • Hindi • Tamil • Telugu • Marathi • English & 90+ Languages
            </p>
            <div className="language-pills-row">
              <span className="lang-tag">ಕನ್ನಡ</span>
              <span className="lang-tag">हिंदी</span>
              <span className="lang-tag">தமிழ்</span>
              <span className="lang-tag">తెలుగు</span>
              <span className="lang-tag">मराठी</span>
              <span className="lang-tag">English</span>
            </div>
          </div>
        ) : (
          <div className="cards-stream">
            {transcripts.map((item) => (
              <div key={item.id} className="transcript-card">
                <div className="card-header">
                  <div className="card-tags">
                    <span className="badge-lang">EN</span>
                    <span className="card-time">
                      {new Date(item.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                    {item.duration && (
                      <span className="card-duration">{item.duration}s</span>
                    )}
                  </div>
                  <button
                    className="card-copy-btn"
                    onClick={() => handleCopySingle(item.id, item.text)}
                    title="Copy sentence"
                  >
                    {copiedId === item.id ? (
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    ) : (
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
                        <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
                      </svg>
                    )}
                  </button>
                </div>
                <div className="card-body">
                  <p className="card-text">{item.text}</p>
                </div>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        )}
      </main>

      {/* Real-time Status Message Bar */}
      <div className={`status-pill-bar ${currentStatus.stateClass}`}>
        <span className="status-live-dot" style={{ backgroundColor: currentStatus.dotColor }}></span>
        <span className="status-live-text">{currentStatus.text}</span>
      </div>

      {/* Modern Centered Bottom Dock */}
      <footer className="dock-footer">
        <div className="dock-center">
          <button
            className={`center-mic-btn ${isCapturing ? 'active' : 'muted'} ${vadState === 'speaking' || micLevel > 10 ? 'speaking' : ''} ${vadState === 'transcribing' ? 'transcribing' : ''}`}
            onClick={handleToggleCapture}
            title={isCapturing ? 'Click to Turn Mic OFF' : 'Click to Turn Mic ON'}
          >
            {/* Live Volume Wave Bars Inside Button */}
            <div className="mic-wave-bars">
              <span className="bar b1" style={{ height: isCapturing && micLevel > 2 ? `${Math.min(22, Math.max(6, micLevel * 0.35))}px` : '6px' }}></span>
              <span className="bar b2" style={{ height: isCapturing && micLevel > 2 ? `${Math.min(28, Math.max(8, micLevel * 0.65))}px` : '8px' }}></span>
              <span className="bar b3" style={{ height: isCapturing && micLevel > 2 ? `${Math.min(22, Math.max(6, micLevel * 0.35))}px` : '6px' }}></span>
            </div>

            <span className="mic-status-label">
              {isCapturing ? 'Mic is ON' : 'Mic is OFF'}
            </span>

            <div className="mic-indicator-dot"></div>
          </button>
        </div>
      </footer>
    </div>
  );
}
