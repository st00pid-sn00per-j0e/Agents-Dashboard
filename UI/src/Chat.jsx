import { useEffect, useRef, useState } from 'react';
import './Chat.css';

const AGENTS = ['Agent_1', 'Agent_2', 'Agent_3'];
const formatTime = (date = new Date()) => date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const SUPERVISOR_API = import.meta.env.VITE_SUPERVISOR_API ?? '/api/chat';
const SUPERVISOR_HEALTH_API = SUPERVISOR_API.replace(/\/chat$/, '/health');

export default function Chat() {
  const [messages, setMessages] = useState([{ id: 1, sender: 'system', text: 'Checking Supervisor connection…', time: formatTime() }]);
  const [input, setInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [previewVersion, setPreviewVersion] = useState(Date.now());
  const listRef = useRef(null);
  useEffect(() => { if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight; }, [messages]);
  useEffect(() => {
    const controller = new AbortController();
    fetch(SUPERVISOR_HEALTH_API, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((health) => setMessages([{ id: 1, sender: 'system', text: health.status === 'ready'
        ? `Supervisor ready · ${health.agents.length} agent(s) available.`
        : 'Supervisor is online but requires reasoning-engine configuration.', time: formatTime() }]))
      .catch(() => setMessages([{ id: 1, sender: 'system', text: 'Supervisor API is offline. Start the local API, then refresh this page.', time: formatTime() }]));
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!isSubmitting) return undefined;
    const refresh = window.setInterval(() => setPreviewVersion(Date.now()), 1200);
    return () => window.clearInterval(refresh);
  }, [isSubmitting]);

  // Refs for canvas/video PIP streaming per agent
  const canvasRefs = useRef([]);
  const videoRefs = useRef([]);
  const pcRefs = useRef([]);
  const fetchIntervals = useRef([]);

  useEffect(() => {
    // Cleanup helper
    const cleanup = () => {
      fetchIntervals.current.forEach((id) => clearInterval(id));
      fetchIntervals.current = [];
      videoRefs.current.forEach((v) => {
        if (v && v.srcObject) {
          v.srcObject.getTracks().forEach(t => t.stop());
          v.srcObject = null;
        }
      });
    };
    if (!isSubmitting) {
      cleanup();
      return undefined;
    }
    // Start periodic fetch->canvas->video capture for each agent
    AGENTS.forEach((agent, idx) => {
      const canvas = canvasRefs.current[idx];
      const video = videoRefs.current[idx];
      if (!canvas || !video) return;
      const ctx = canvas.getContext('2d');
      // set a reasonable size; adapt to CSS
      const W = 320, H = 180;
      canvas.width = W; canvas.height = H;
      let active = true;
      const drawFrame = async () => {
        if (!active) return;
        try {
          const res = await fetch(`/api/previews/${agent}.png?frame=${Date.now()}`);
          if (!res.ok) return;
          const blob = await res.blob();
          const bitmap = await createImageBitmap(blob);
          ctx.clearRect(0,0,W,H);
          ctx.drawImage(bitmap, 0, 0, W, H);
          bitmap.close?.();
        } catch (e) {
          // ignore fetch errors
        }
      };
      // initial draw and interval
      drawFrame();
      const id = setInterval(drawFrame, 1200);
      fetchIntervals.current[idx] = id;
      // hook up canvas stream to video
      const stream = canvas.captureStream(24);
      video.srcObject = stream;
      video.play().catch(()=>{});
    });

    return () => {
      // cleanup when effect tears down
      fetchIntervals.current.forEach((id) => clearInterval(id));
      fetchIntervals.current = [];
      videoRefs.current.forEach((v) => {
        if (v && v.srcObject) {
          v.srcObject.getTracks().forEach(t => t.stop());
          v.srcObject = null;
        }
      });
      // close any peer connections
      pcRefs.current.forEach((pc) => {
        try { pc.close(); } catch(e) {}
      });
      pcRefs.current = [];
    };
  }, [isSubmitting]);

  const openPictureInPicture = async (idx) => {
    const agent = AGENTS[idx];

    // Prefer server-backed WebRTC stream (low-latency) if available
    try {
      // Reuse existing PC if present
      let pc = pcRefs.current[idx];
      let videoEl = videoRefs.current[idx];
      if (!videoEl) return;
      if (!pc) {
        pc = new RTCPeerConnection();
        pcRefs.current[idx] = pc;
        pc.ontrack = (ev) => {
          try {
            // attach first track into a MediaStream
            const ms = new MediaStream(ev.streams?.[0]?.getTracks() ?? ev.track ? [ev.track] : []);
            videoEl.srcObject = ms;
            videoEl.play().catch(()=>{});
            // when track arrives, request PiP
            (async () => {
              try {
                await videoEl.requestPictureInPicture();
              } catch (err) {
                console.warn('PiP request failed:', err);
              }
            })();
          } catch (e) {
            console.warn('ontrack attach failed', e);
          }
        };

        // create offer and POST to server signaling endpoint
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        const res = await fetch(`/api/webrtc/${agent}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type }),
        });
        if (!res.ok) throw new Error('Signaling failed');
        const answer = await res.json();
        await pc.setRemoteDescription({ sdp: answer.sdp, type: answer.type });
      } else {
        // already have pc and video attached; request PiP directly
        try {
          await videoEl.requestPictureInPicture();
        } catch (err) {
          console.warn('PiP request failed', err);
        }
      }
      return;
    } catch (err) {
      // If WebRTC failed or server doesn't support it, fallback to canvas-based local PiP
      console.warn('WebRTC PiP failed, falling back to canvas capture:', err);
    }

    // Fallback to local canvas->video PiP (previous behavior)
    const video = videoRefs.current[idx];
    if (!video) return;
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      }
      await video.requestPictureInPicture();
    } catch (err) {
      console.warn('Picture-in-Picture failed', err);
    }
  };

  const sendMessage = async (event) => {
    event.preventDefault();
    const text = input.trim();
    if (!text) return;
    const requestId = Date.now();
    setMessages((current) => [...current, { id: requestId, sender: 'You', text, time: formatTime() }]);
    setInput('');
    setIsSubmitting(true);
    try {
      const response = await fetch(SUPERVISOR_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'The supervisor rejected the request.');
      const route = payload.mode === 'dispatch' && payload.agents?.length
        ? `Dispatched to ${payload.agents.join(', ')}`
        : 'Supervisor response';
      const agentMessages = Object.entries(payload.agent_outputs ?? {}).map(([agent, output], index) => ({
        id: requestId + index + 1,
        sender: agent,
        text: output,
        time: formatTime(),
        route: 'Agent response',
      }));
      setMessages((current) => [
        ...current,
        ...agentMessages,
        { id: requestId + agentMessages.length + 1, sender: 'Supervisor', text: payload.reply, time: formatTime(), route },
      ]);
    } catch (error) {
      const unavailable = error instanceof TypeError;
      const message = unavailable
        ? 'Supervisor API is offline. Start .\\.venv\\Scripts\\python.exe src\\SupervisorAPI.py from the repository root, then retry.'
        : (error.message || 'Unable to complete this Supervisor request.');
      setMessages((current) => [...current, { id: requestId + 1, sender: 'system', text: message, time: formatTime() }]);
    } finally {
      setIsSubmitting(false);
    }
  };
  return <section className="chat-section" id="chat">
    <h2 className="section-title"><span className="chat-eyebrow">Ops console</span>Agent chat</h2>
    {isSubmitting && <>
      <section className="preview-dock" aria-label="Live agent browser previews">
        <div className="preview-heading"><span className="live-dot" /> Live browser previews <small>refreshing every 1.2s</small></div>
        <div className="preview-grid">{AGENTS.map((agent) => <article className="browser-preview" key={agent}>
          <div className="browser-chrome"><span><i /><i /><i /></span><strong>{agent}</strong><em>LIVE</em></div>
          <div className="preview-viewport">
            <img src={`/api/previews/${agent}.png?frame=${previewVersion}`} alt={`${agent} live browser preview`} onError={(event) => event.currentTarget.classList.add('is-unavailable')} onLoad={(event) => event.currentTarget.classList.remove('is-unavailable')} />
            <span className="preview-waiting">Waiting for browser frame…</span>
          </div>
        </article>)}</div>
      </section>

      {/* Floating picture-in-picture (PIP) windows for each agent */}
      <div className="pip-container" aria-hidden={!isSubmitting}>
        {AGENTS.map((agent, idx) => (
          <div key={agent} className={`pip-window pip-${idx+1}`} role="dialog" aria-label={`${agent} floating preview`}>
            <div className="pip-header">
              <strong>{agent}</strong>
              <div className="pip-controls">
                <button type="button" className="pip-pip-btn" onClick={() => openPictureInPicture(idx)}>PiP</button>
                <span className="pip-live">LIVE</span>
              </div>
            </div>
            <div className="pip-body">
              <video ref={(el) => (videoRefs.current[idx] = el)} muted playsInline autoPlay />
              {/* hidden canvas used to compose frames into a MediaStream for PiP */}
              <canvas ref={(el) => (canvasRefs.current[idx] = el)} style={{ display: 'none' }} />
            </div>
          </div>
        ))}
      </div>
    </>}
    <div className="chat-shell">
      <aside className="chat-side"><div className="agents-list"><h4>Available agents</h4>{AGENTS.map((agent) => <span key={agent} className="agent-btn">{agent}<i /></span>)}</div><div className="chat-info"><p>Routing: <strong>Supervisor</strong></p><p>The supervisor chooses the relevant agents for each task.</p></div></aside>
      <main className="chat-main"><div className="messages" ref={listRef} data-testid="messages-list">{messages.map((message) => <div key={message.id} className={`message ${message.sender === 'You' ? 'msg-user' : message.sender === 'system' ? 'msg-system' : 'msg-agent'}`}><div className="message-meta"><span className="message-sender">{message.sender}</span>{message.route && <span className="message-route">{message.route}</span>}<span className="message-time">{message.time}</span></div><div className="message-body">{message.text}</div></div>)}</div>
        <form className="chat-input" onSubmit={sendMessage}><div className="input-controls"><div className="routing-label">Supervisor routing</div><input type="text" placeholder="Ask the supervisor to coordinate a task..." value={input} onChange={(event) => setInput(event.target.value)} aria-label="Chat input" disabled={isSubmitting} /><button type="submit" className="send-btn" disabled={isSubmitting}>{isSubmitting ? 'Working…' : 'Send'}</button></div></form>
      </main>
    </div>
  </section>;
}
