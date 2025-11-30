/**
 * Command Widget Component
 *
 * Shows rich UI widgets for different command types
 * (npm install progress, test results, build status, etc.)
 */

import { useState, useEffect } from "react";
import { CommandExecution, TestRun, formatDuration } from "../../types/agent";

interface CommandWidgetProps {
  command?: CommandExecution;
  testRun?: TestRun;
  type: "command" | "test" | "install" | "build";
  expanded?: boolean;
}

export function CommandWidget({ command, testRun, type, expanded = true }: CommandWidgetProps) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isRunning, setIsRunning] = useState(false);

  // Update elapsed time for running commands
  useEffect(() => {
    if (command && command.status === "running") {
      setIsRunning(true);
      const startTime = new Date(command.start_time).getTime();
      const interval = setInterval(() => {
        const elapsed = (Date.now() - startTime) / 1000;
        setElapsedTime(elapsed);
      }, 100);
      return () => clearInterval(interval);
    } else if (testRun && !testRun.end_time) {
      setIsRunning(true);
      const startTime = new Date(testRun.start_time).getTime();
      const interval = setInterval(() => {
        const elapsed = (Date.now() - startTime) / 1000;
        setElapsedTime(elapsed);
      }, 100);
      return () => clearInterval(interval);
    } else {
      setIsRunning(false);
    }
  }, [command, testRun]);

  // Render based on type
  if (type === "test" && testRun) {
    return <TestWidget testRun={testRun} elapsedTime={elapsedTime} expanded={expanded} />;
  }

  if (command) {
    const widgetType = detectCommandType(command.command);

    switch (widgetType) {
      case "install":
        return <InstallWidget command={command} elapsedTime={elapsedTime} expanded={expanded} />;
      case "build":
        return <BuildWidget command={command} elapsedTime={elapsedTime} expanded={expanded} />;
      case "git":
        return <GitWidget command={command} expanded={expanded} />;
      default:
        return <GenericCommandWidget command={command} elapsedTime={elapsedTime} expanded={expanded} />;
    }
  }

  return null;
}

// Install Widget (npm, pip, yarn)
function InstallWidget({ command, elapsedTime, expanded }: {
  command: CommandExecution;
  elapsedTime: number;
  expanded: boolean;
}) {
  const isRunning = command.status === "running";
  const packages = extractPackages(command.command);

  return (
    <div className="command-widget command-widget--install">
      <div className="command-widget__header">
        <span className="command-widget__icon">📦</span>
        <span className="command-widget__title">Installing packages...</span>
        {isRunning && (
          <span className="command-widget__time">{formatDuration(elapsedTime)}</span>
        )}
      </div>

      {expanded && (
        <div className="command-widget__content">
          <div className="command-widget__packages">
            {packages.map((pkg, idx) => (
              <span key={idx} className="command-widget__package">{pkg}</span>
            ))}
          </div>

          {isRunning && (
            <div className="command-widget__progress">
              <div className="command-widget__progress-bar">
                <div className="command-widget__progress-fill command-widget__progress-fill--indeterminate" />
              </div>
              <span className="command-widget__progress-text">Installing...</span>
            </div>
          )}

          {command.status === "completed" && (
            <div className="command-widget__status command-widget__status--success">
              ✅ Installed successfully
            </div>
          )}

          {command.status === "failed" && (
            <div className="command-widget__status command-widget__status--error">
              ❌ Installation failed (exit code: {command.exit_code})
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Test Widget
function TestWidget({ testRun, elapsedTime, expanded }: {
  testRun: TestRun;
  elapsedTime: number;
  expanded: boolean;
}) {
  const isRunning = !testRun.end_time;
  const successRate = testRun.success_rate * 100;

  return (
    <div className="command-widget command-widget--test">
      <div className="command-widget__header">
        <span className="command-widget__icon">🧪</span>
        <span className="command-widget__title">
          {testRun.tool} {isRunning ? "running..." : "results"}
        </span>
        {isRunning && (
          <span className="command-widget__time">{formatDuration(elapsedTime)}</span>
        )}
      </div>

      {expanded && (
        <div className="command-widget__content">
          <div className="command-widget__test-stats">
            <div className="command-widget__test-stat command-widget__test-stat--passed">
              <span className="command-widget__test-stat-value">{testRun.passed_tests}</span>
              <span className="command-widget__test-stat-label">passed</span>
            </div>

            {testRun.failed_tests > 0 && (
              <div className="command-widget__test-stat command-widget__test-stat--failed">
                <span className="command-widget__test-stat-value">{testRun.failed_tests}</span>
                <span className="command-widget__test-stat-label">failed</span>
              </div>
            )}

            {testRun.skipped_tests > 0 && (
              <div className="command-widget__test-stat command-widget__test-stat--skipped">
                <span className="command-widget__test-stat-value">{testRun.skipped_tests}</span>
                <span className="command-widget__test-stat-label">skipped</span>
              </div>
            )}
          </div>

          {testRun.total_tests > 0 && (
            <div className="command-widget__progress">
              <div className="command-widget__progress-bar">
                <div
                  className="command-widget__progress-fill command-widget__progress-fill--success"
                  style={{ width: `${successRate}%` }}
                />
              </div>
              <span className="command-widget__progress-text">
                {successRate.toFixed(0)}% success rate
              </span>
            </div>
          )}

          {testRun.failures.length > 0 && (
            <details className="command-widget__failures">
              <summary>Failed tests ({testRun.failures.length})</summary>
              {testRun.failures.slice(0, 5).map((failure: any, idx: number) => (
                <div key={idx} className="command-widget__failure">
                  {failure.test || failure.file}
                </div>
              ))}
            </details>
          )}
        </div>
      )}
    </div>
  );
}

// Build Widget
function BuildWidget({ command, elapsedTime, expanded }: {
  command: CommandExecution;
  elapsedTime: number;
  expanded: boolean;
}) {
  const isRunning = command.status === "running";

  return (
    <div className="command-widget command-widget--build">
      <div className="command-widget__header">
        <span className="command-widget__icon">🔨</span>
        <span className="command-widget__title">Building project...</span>
        {isRunning && (
          <span className="command-widget__time">{formatDuration(elapsedTime)}</span>
        )}
      </div>

      {expanded && (
        <div className="command-widget__content">
          <div className="command-widget__command">{command.command}</div>

          {isRunning && (
            <div className="command-widget__progress">
              <div className="command-widget__progress-bar">
                <div className="command-widget__progress-fill command-widget__progress-fill--indeterminate" />
              </div>
              <span className="command-widget__progress-text">Building...</span>
            </div>
          )}

          {command.status === "completed" && (
            <div className="command-widget__status command-widget__status--success">
              ✅ Build successful
            </div>
          )}

          {command.status === "failed" && (
            <div className="command-widget__status command-widget__status--error">
              ❌ Build failed (exit code: {command.exit_code})
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Git Widget
function GitWidget({ command, expanded }: {
  command: CommandExecution;
  expanded: boolean;
}) {
  const gitCommand = command.command.split(" ")[1] || "operation";
  const icon = getGitIcon(gitCommand);

  return (
    <div className="command-widget command-widget--git">
      <div className="command-widget__header">
        <span className="command-widget__icon">{icon}</span>
        <span className="command-widget__title">Git {gitCommand}</span>
      </div>

      {expanded && (
        <div className="command-widget__content">
          <div className="command-widget__command">{command.command}</div>

          {command.status === "completed" && (
            <div className="command-widget__status command-widget__status--success">
              ✅ Completed
            </div>
          )}

          {command.status === "failed" && (
            <div className="command-widget__status command-widget__status--error">
              ❌ Failed (exit code: {command.exit_code})
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Generic Command Widget
function GenericCommandWidget({ command, elapsedTime, expanded }: {
  command: CommandExecution;
  elapsedTime: number;
  expanded: boolean;
}) {
  const isRunning = command.status === "running";

  return (
    <div className="command-widget command-widget--generic">
      <div className="command-widget__header">
        <span className="command-widget__icon">🚀</span>
        <span className="command-widget__title">
          {command.command.split(" ")[0]}
        </span>
        {isRunning && (
          <span className="command-widget__time">{formatDuration(elapsedTime)}</span>
        )}
      </div>

      {expanded && (
        <div className="command-widget__content">
          <div className="command-widget__command">{command.command}</div>

          {isRunning && (
            <div className="command-widget__status command-widget__status--running">
              ⚡ Running...
            </div>
          )}

          {command.status === "completed" && (
            <div className="command-widget__status command-widget__status--success">
              ✅ Completed
            </div>
          )}

          {command.status === "failed" && (
            <div className="command-widget__status command-widget__status--error">
              ❌ Failed (exit code: {command.exit_code})
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Helper functions

function detectCommandType(command: string): string {
  if (command.match(/^(npm|yarn|pnpm|pip|pipenv|poetry)\s+(install|add)/)) {
    return "install";
  }
  if (command.match(/^(make|cmake|cargo build|go build|npm run build)/)) {
    return "build";
  }
  if (command.match(/^git\s+/)) {
    return "git";
  }
  if (command.match(/^(pytest|jest|mocha|npm test|yarn test)/)) {
    return "test";
  }
  return "generic";
}

function extractPackages(command: string): string[] {
  const parts = command.split(/\s+/);
  const installIdx = parts.findIndex(p => p === "install" || p === "add");
  if (installIdx >= 0) {
    return parts.slice(installIdx + 1).filter(p => !p.startsWith("-"));
  }
  return [];
}

function getGitIcon(command: string): string {
  const icons: Record<string, string> = {
    status: "📊",
    diff: "🔍",
    commit: "📝",
    push: "⬆️",
    pull: "⬇️",
    add: "➕",
    checkout: "🔀",
    branch: "🌿",
    merge: "🔗",
  };
  return icons[command] || "📋";
}