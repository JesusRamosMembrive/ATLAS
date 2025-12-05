import { TerminalSocketIO, terminalSocketIOStyles } from "./TerminalSocketIO";

/**
 * Remote Terminal View Page
 *
 * Full-page terminal view with security warning.
 * Uses Socket.IO for reliable PTY communication.
 */
export function RemoteTerminalView() {
  return (
    <div className="terminal-view">
      <style>{terminalSocketIOStyles}</style>

      {/* Terminal Container */}
      <div className="terminal-page-container">
        <TerminalSocketIO
          welcomeMessage="AEGIS Remote Terminal"
          height="600px"
          className="terminal-page-embed"
        />
      </div>

      {/* Security Warning */}
      <section className="terminal-warning-section">
        <div className="terminal-warning">
          <div className="terminal-warning-icon">⚠️</div>
          <div className="terminal-warning-content">
            <h3>Security Notice</h3>
            <p>
              This terminal has full access to your system with the same
              permissions as the backend process. Only use on trusted networks
              and be careful with sensitive operations.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
