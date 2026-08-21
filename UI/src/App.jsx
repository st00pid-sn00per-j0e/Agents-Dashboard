import { useState, useEffect, useRef, useMemo } from 'react';

const ASCII_LOGO = `
 ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
 ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
 ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
 ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
 ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
 ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
`;

const ASCII_SUBTITLE = `
    E M E R G E N T   N E X U S
`;

const AGENT_FRAMES = [
  `
    ╔══════════════════╗
    ║  ▓▓▓▓▓▓▓▓▓▓▓▓▓  ║
    ║  ▓  AGENT_1  ▓  ║
    ║  ▓  [RUNNING] ▓  ║
    ║  ▓▓▓▓▓▓▓▓▓▓▓▓▓  ║
    ╚══════════════════╝
  `,
  `
    ╔══════════════════╗
    ║  ░░░░░░░░░░░░░  ║
    ║  ░  AGENT_1  ░  ║
    ║  ░  [RUNNING] ░  ║
    ║  ░░░░░░░░░░░░░  ║
    ╚══════════════════╝
  `,
  `
    ╔══════════════════╗
    ║  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ║
    ║  ▒  AGENT_1  ▒  ║
    ║  ▒  [RUNNING] ▒  ║
    ║  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ║
    ╚══════════════════╝
  `,
];

const AGENT_2_FRAMES = [
  `
    ╔══════════════════╗
    ║  ██████████████  ║
    ║  █  AGENT_2  █  ║
    ║  █  [IDLE]    █  ║
    ║  ██████████████  ║
    ╚══════════════════╝
  `,
  `
    ╔══════════════════╗
    ║  ▓▓▓▓▓▓▓▓▓▓▓▓▓  ║
    ║  ▓  AGENT_2  ▓  ║
    ║  ▓  [IDLE]    ▓  ║
    ║  ▓▓▓▓▓▓▓▓▓▓▓▓▓  ║
    ╚══════════════════╝
  `,
  `
    ╔══════════════════╗
    ║  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ║
    ║  ▒  AGENT_2  ▒  ║
    ║  ▒  [IDLE]    ▒  ║
    ║  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ║
    ╚══════════════════╝
  `,
];

const AGENT_3_FRAMES = [
  `
    ╔══════════════════╗
    ║  ░░░░░░░░░░░░░  ║
    ║  ░  AGENT_3  ░  ║
    ║  ░  [ERROR]   ░  ║
    ║  ░░░░░░░░░░░░░  ║
    ╚══════════════════╝
  `,
  `
    ╔══════════════════╗
    ║  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ║
    ║  ▒  AGENT_3  ▒  ║
    ║  ▒  [ERROR]   ▒  ║
    ║  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ║
    ╚══════════════════╝
  `,
  `
    ╔══════════════════╗
    ║  ▓▓▓▓▓▓▓▓▓▓▓▓▓  ║
    ║  ▓  AGENT_3  ▓  ║
    ║  ▓  [ERROR]   ▓  ║
    ║  ▓▓▓▓▓▓▓▓▓▓▓▓▓  ║
    ╚══════════════════╝
  `,
];

const TERMINAL_FRAMES = [
  '> _',
  '> > _',
  '> > > _',
  '> > > > _',
  '> > > > > _',
  '> > > > _',
  '> > > _',
  '> > _',
  '> _',
  '> _',
];

const DATA_STREAM = `
╔══════════════════════════════════════════════════════════════╗
║  > Initializing neural pathways...          [OK]            ║
║  > Loading agent modules...                 [OK]            ║
║  > Establishing secure connections...        [OK]            ║
║  > Reasoning engine online...                [OK]            ║
╚══════════════════════════════════════════════════════════════╝
`;

const INITIAL_TASKS = [
  { id: 1, task: 'Scrape financial data from NYSE', status: 'running', agent: 'Agent_1', progress: 67 },
  { id: 2, task: 'Analyze market trends', status: 'completed', agent: 'Agent_2', progress: 100 },
  { id: 3, task: 'Generate quarterly report', status: 'pending', agent: 'Agent_3', progress: 0 },
  { id: 4, task: 'Optimize trading algorithm', status: 'running', agent: 'Agent_1', progress: 34 },
];

function useAsciiAnimation(frames, speed = 200) {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => {
      setFrame(f => (f + 1) % frames.length);
    }, speed);
    return () => clearInterval(interval);
  }, [frames, speed]);
  return frames[frame];
}

function AsciiLogo() {
  const [glitch, setGlitch] = useState(false);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setGlitch(true);
      setTimeout(() => setGlitch(false), 200);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="logo-container">
      <div className={`logo-wrapper ${glitch ? 'glitch-active' : ''}`}>
        <pre className={`ascii-logo ${glitch ? 'animate-glitch' : ''}`}>
          {ASCII_LOGO}
        </pre>
      </div>
      <pre className="ascii-subtitle">
        {ASCII_SUBTITLE}
      </pre>
    </div>
  );
}

function AgentCard3D({ name, frames, status, delay }) {
  const [hovered, setHovered] = useState(false);
  const [stats] = useState(() => ({
    cpu: Math.floor(Math.random() * 60) + 20,
    mem: Math.floor(Math.random() * 40) + 30,
    net: Math.floor(Math.random() * 50) + 10,
  }));
  const currentFrame = useAsciiAnimation(frames, 300 + delay);
  
  const statusColors = {
    running: 'var(--accent-green)',
    idle: 'var(--accent-cyan)',
    error: 'var(--accent-red)',
    pending: 'var(--accent-orange)',
  };

  return (
    <div 
      className="agent-card-3d"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ '--card-color': statusColors[status] || 'var(--text-primary)' }}
    >
      <div className={`card-inner ${hovered ? 'flipped' : ''}`}>
        <div className="card-front">
          <div className="card-glow" />
          <div className="ascii-art-container">
            <pre 
              className="ascii-art" 
              style={{ color: statusColors[status] }}
            >
              {currentFrame}
            </pre>
          </div>
          <div className="card-info">
            <h3 className="agent-name">{name}</h3>
            <span className="agent-status" style={{ color: statusColors[status] }}>
              {status.toUpperCase()}
            </span>
          </div>
        </div>
        <div className="card-back">
          <h3 className="agent-name">{name}</h3>
          <div className="back-content">
            <div className="stat-row">
              <span>CPU</span>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${stats.cpu}%` }} />
              </div>
            </div>
            <div className="stat-row">
              <span>MEM</span>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${stats.mem}%` }} />
              </div>
            </div>
            <div className="stat-row">
              <span>NET</span>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${stats.net}%` }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TerminalAnimation() {
  const currentFrame = useAsciiAnimation(TERMINAL_FRAMES, 150);
  const [dataVisible, setDataVisible] = useState(true);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setDataVisible(v => !v);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="terminal-container">
      <div className="terminal-header">
        <div className="terminal-dots">
          <span className="dot red" />
          <span className="dot yellow" />
          <span className="dot green" />
        </div>
        <span className="terminal-title">nexus@nizarai:~</span>
      </div>
      <div className="terminal-body">
        <div className="terminal-line">
          <span className="prompt">$</span>
          <span className="command">{currentFrame}</span>
          <span className="cursor" />
        </div>
        {dataVisible && (
          <pre className="terminal-data">
            {DATA_STREAM}
          </pre>
        )}
      </div>
    </div>
  );
}

function TaskCard3D({ task, onStatusChange }) {
  const statusColors = {
    running: 'var(--accent-green)',
    completed: 'var(--accent-cyan)',
    pending: 'var(--accent-orange)',
  };

  return (
    <div 
      className="task-card-3d"
      style={{ '--card-color': statusColors[task.status] || 'var(--text-primary)' }}
    >
      <div className="task-card-inner">
        <div className="task-header">
          <span className="task-id">#{task.id.toString().padStart(3, '0')}</span>
          <span 
            className="task-status" 
            style={{ color: statusColors[task.status] }}
          >
            {task.status.toUpperCase()}
          </span>
        </div>
        <div className="task-body">
          <p className="task-description">{task.task}</p>
          <div className="task-meta">
            <span className="task-agent">🤖 {task.agent}</span>
          </div>
        </div>
        <div className="task-progress">
          <div className="progress-track">
            <div 
              className="progress-bar-fill"
              style={{ 
                width: `${task.progress}%`,
                backgroundColor: statusColors[task.status]
              }}
            />
          </div>
          <span className="progress-text">{task.progress}%</span>
        </div>
        <div className="task-actions">
          <button 
            className="task-btn"
            onClick={() => onStatusChange(task.id, 'running')}
            disabled={task.status === 'running'}
          >
            ▶ Run
          </button>
          <button 
            className="task-btn"
            onClick={() => onStatusChange(task.id, 'completed')}
            disabled={task.status === 'completed'}
          >
            ✓ Complete
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateTaskModal({ onClose, onCreate }) {
  const [taskName, setTaskName] = useState('');
  const [agent, setAgent] = useState('Agent_1');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!taskName.trim()) return;
    onCreate({ task: taskName, agent });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Task</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Task Description</label>
            <input
              type="text"
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              placeholder="Enter task description..."
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>Assign To</label>
            <select value={agent} onChange={(e) => setAgent(e.target.value)}>
              <option value="Agent_1">Agent_1</option>
              <option value="Agent_2">Agent_2</option>
              <option value="Agent_3">Agent_3</option>
            </select>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn-secondary-3d" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary-3d">
              <span className="btn-text">Create Task</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Webflow3DShowcase() {
  const [activeShape, setActiveShape] = useState('cube');

  return (
    <section className="webflow-3d-section">
      <h2 className="section-title">
        <span className="title-icon">🧊</span>
        Webflow 3D Animation
        <span className="title-line" />
      </h2>
      <div className="webflow-3d-container">
        <div className="webflow-scene" style={{ perspective: '1200px' }}>
          <div className={`webflow-object ${activeShape === 'cube' ? 'active' : ''}`}>
            <div className="cube-face front">FRONT</div>
            <div className="cube-face back">BACK</div>
            <div className="cube-face right">RIGHT</div>
            <div className="cube-face left">LEFT</div>
            <div className="cube-face top">TOP</div>
            <div className="cube-face bottom">BOTTOM</div>
          </div>
          <div className={`webflow-object torus ${activeShape === 'torus' ? 'active' : ''}`}>
            <div className="torus-ring" />
            <div className="torus-ring ring-2" />
            <div className="torus-ring ring-3" />
          </div>
          <div className={`webflow-object plane ${activeShape === 'plane' ? 'active' : ''}`}>
            <div className="plane-face" />
            <div className="plane-face face-2" />
            <div className="plane-face face-3" />
          </div>
        </div>
        <div className="webflow-controls">
          <button 
            className={`webflow-btn ${activeShape === 'cube' ? 'active' : ''}`}
            onClick={() => setActiveShape('cube')}
          >
            Cube
          </button>
          <button 
            className={`webflow-btn ${activeShape === 'torus' ? 'active' : ''}`}
            onClick={() => setActiveShape('torus')}
          >
            Torus
          </button>
          <button 
            className={`webflow-btn ${activeShape === 'plane' ? 'active' : ''}`}
            onClick={() => setActiveShape('plane')}
          >
            Planes
          </button>
        </div>
      </div>
    </section>
  );
}

function NetworkGraph() {
  const canvasRef = useRef(null);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;
    let nodes = [];
    
    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);
    
    for (let i = 0; i < 15; i++) {
      nodes.push({
        x: Math.random() * canvas.offsetWidth,
        y: Math.random() * canvas.offsetHeight,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
      });
    }
    
    const draw = () => {
      ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
      
      nodes.forEach((node, i) => {
        node.x += node.vx;
        node.y += node.vy;
        if (node.x < 0 || node.x > canvas.offsetWidth) node.vx *= -1;
        if (node.y < 0 || node.y > canvas.offsetHeight) node.vy *= -1;
        
        nodes.forEach((other, j) => {
          if (i === j) return;
          const dx = node.x - other.x;
          const dy = node.y - other.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 100) {
            ctx.beginPath();
            ctx.moveTo(node.x, node.y);
            ctx.lineTo(other.x, other.y);
            ctx.strokeStyle = `rgba(0, 230, 166, ${0.3 * (1 - dist / 100)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        });
        
        ctx.beginPath();
        ctx.arc(node.x, node.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#00E6A6';
        ctx.fill();
      });
      
      animationId = requestAnimationFrame(draw);
    };
    
    draw();
    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationId);
    };
  }, []);

  return <canvas ref={canvasRef} className="network-canvas" />;
}

function Navbar({ onNewTask }) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  
  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { href: '#dashboard', label: 'Dashboard' },
    { href: '#agents', label: 'Agents' },
    { href: '#tasks', label: 'Tasks' },
    { href: '#logs', label: 'Logs' },
  ];

  return (
    <nav className={`navbar ${scrolled ? 'scrolled' : ''}`}>
      <div className="nav-brand">
        <span className="nav-logo">⚡</span>
        <span className="nav-title">Nizami Emergent Nexus</span>
      </div>
      
      <div className={`nav-links ${mobileOpen ? 'mobile-open' : ''}`}>
        {navLinks.map(link => (
          <a key={link.href} href={link.href} className="nav-link active">
            {link.label}
          </a>
        ))}
      </div>

      <div className="nav-actions">
        <button className="nav-btn-3d" onClick={onNewTask}>
          <span>+ New Task</span>
        </button>
        <button 
          className="mobile-toggle"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          <span className={`hamburger ${mobileOpen ? 'open' : ''}`}>
            <span />
            <span />
            <span />
          </span>
        </button>
      </div>
    </nav>
  );
}

function App() {
  const [tasks, setTasks] = useState(INITIAL_TASKS);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [notification, setNotification] = useState(null);

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const handleCreateTask = ({ task, agent }) => {
    const newTask = {
      id: Date.now(),
      task,
      status: 'pending',
      agent,
      progress: 0,
    };
    setTasks(prev => [newTask, ...prev]);
    showNotification(`Task created and assigned to ${agent}`);
  };

  const handleStatusChange = (id, status) => {
    setTasks(prev => prev.map(t => {
      if (t.id !== id) return t;
      let progress = t.progress;
      if (status === 'running') progress = Math.max(progress, 10);
      if (status === 'completed') progress = 100;
      return { ...t, status, progress };
    }));
    const task = tasks.find(t => t.id === id);
    if (task) {
      showNotification(`Task #${id.toString().padStart(3, '0')} marked as ${status}`);
    }
  };

  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      const matchesSearch = task.task.toLowerCase().includes(searchQuery.toLowerCase()) ||
                           task.agent.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesFilter = filterStatus === 'all' || task.status === filterStatus;
      return matchesSearch && matchesFilter;
    });
  }, [tasks, searchQuery, filterStatus]);

  const stats = useMemo(() => {
    const running = tasks.filter(t => t.status === 'running').length;
    const completed = tasks.filter(t => t.status === 'completed').length;
    const pending = tasks.filter(t => t.status === 'pending').length;
    return { running, completed, pending, total: tasks.length };
  }, [tasks]);

  return (
    <div className="app">
      <Navbar onNewTask={() => setShowCreateModal(true)} />
      
      {notification && (
        <div className={`notification ${notification.type}`}>
          {notification.message}
        </div>
      )}

      {showCreateModal && (
        <CreateTaskModal 
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreateTask}
        />
      )}
      
      <main className="main-content">
        <section className="hero-section">
          <AsciiLogo />
          <div className="hero-actions">
            <button className="btn-primary-3d" onClick={() => setShowCreateModal(true)}>
              <span className="btn-text">Launch New Task</span>
              <span className="btn-glow" />
            </button>
            <button className="btn-secondary-3d" onClick={() => document.getElementById('logs').scrollIntoView({ behavior: 'smooth' })}>
              <span className="btn-text">View Logs</span>
            </button>
          </div>
        </section>

        <section className="stats-section">
          <div className="stats-grid">
            <div className="stat-card-3d" style={{ '--stat-color': 'var(--accent-green)' }}>
              <div className="stat-icon">🤖</div>
              <div className="stat-content">
                <div className="stat-value">3</div>
                <div className="stat-label">Active Agents</div>
              </div>
              <div className="stat-glow" />
            </div>
            <div className="stat-card-3d" style={{ '--stat-color': 'var(--accent-cyan)' }}>
              <div className="stat-icon">📋</div>
              <div className="stat-content">
                <div className="stat-value">{stats.total}</div>
                <div className="stat-label">Total Tasks</div>
              </div>
              <div className="stat-glow" />
            </div>
            <div className="stat-card-3d" style={{ '--stat-color': 'var(--accent-purple)' }}>
              <div className="stat-icon">⚡</div>
              <div className="stat-content">
                <div className="stat-value">{stats.running}</div>
                <div className="stat-label">Running</div>
              </div>
              <div className="stat-glow" />
            </div>
            <div className="stat-card-3d" style={{ '--stat-color': 'var(--accent-orange)' }}>
              <div className="stat-icon">✅</div>
              <div className="stat-content">
                <div className="stat-value">{stats.completed}</div>
                <div className="stat-label">Completed</div>
              </div>
              <div className="stat-glow" />
            </div>
          </div>
        </section>

        <section className="agents-section" id="agents">
          <h2 className="section-title">
            <span className="title-icon">🤖</span>
            Active Agents
            <span className="title-line" />
          </h2>
          <div className="agents-grid">
            <AgentCard3D name="Agent_1" frames={AGENT_FRAMES} status="running" delay={0} />
            <AgentCard3D name="Agent_2" frames={AGENT_2_FRAMES} status="idle" delay={100} />
            <AgentCard3D name="Agent_3" frames={AGENT_3_FRAMES} status="error" delay={200} />
          </div>
        </section>

        <section className="tasks-section" id="tasks">
          <div className="tasks-header">
            <h2 className="section-title">
              <span className="title-icon">📋</span>
              Task Queue
              <span className="title-line" />
            </h2>
            <div className="tasks-controls">
              <div className="search-box">
                <span className="search-icon">🔍</span>
                <input
                  type="text"
                  placeholder="Search tasks..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <select 
                className="filter-select"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="all">All Status</option>
                <option value="running">Running</option>
                <option value="completed">Completed</option>
                <option value="pending">Pending</option>
                <option value="error">Error</option>
              </select>
              <button className="btn-primary-3d" onClick={() => setShowCreateModal(true)}>
                <span className="btn-text">+ New</span>
              </button>
            </div>
          </div>
          <div className="tasks-grid">
            {filteredTasks.map(task => (
              <TaskCard3D 
                key={task.id} 
                task={task} 
                onStatusChange={handleStatusChange}
              />
            ))}
            {filteredTasks.length === 0 && (
              <div className="empty-state">
                <p>No tasks found matching your criteria</p>
              </div>
            )}
          </div>
        </section>

        <section className="terminal-section" id="logs">
          <h2 className="section-title">
            <span className="title-icon">💻</span>
            Terminal Output
            <span className="title-line" />
          </h2>
          <div className="terminal-wrapper">
            <TerminalAnimation />
          </div>
        </section>

        <section className="network-section">
          <h2 className="section-title">
            <span className="title-icon">🌐</span>
            Network Activity
            <span className="title-line" />
          </h2>
          <div className="network-wrapper">
            <NetworkGraph />
          </div>
        </section>

        <Webflow3DShowcase />
      </main>

      <footer className="footer">
        <p>© 2026 Nizami Emergent Nexus. All rights reserved.</p>
      </footer>
    </div>
  );
}

export default App;
