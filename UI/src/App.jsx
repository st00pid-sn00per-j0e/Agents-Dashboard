import Chat from './Chat';

function App() {
  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#chat" aria-label="Nexus Supervisor console">
          <span className="brand-mark">N</span>
          <span>NEXUS <em>SUPERVISOR</em></span>
        </a>
        <div className="system-state"><span className="live-dot" /> Unified agent console</div>
      </header>
      <main className="main-content">
        <section className="console-intro">
          <p className="eyebrow">Unified orchestration</p>
          <h1>What would you like the team to do?</h1>
          <p>Send one task to the Supervisor. It decides whether to answer directly or delegate to the relevant agents.</p>
        </section>
        <Chat />
      </main>
      <footer>Local Supervisor Console</footer>
    </div>
  );
}

export default App;
