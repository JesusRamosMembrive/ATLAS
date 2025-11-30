import { useState } from "react";

interface BackendUrlSectionProps {
  backendUrl: string;
  disabled: boolean;
  onBackendUrlChange: (value: string) => void;
}

export function BackendUrlSection({
  backendUrl,
  disabled,
  onBackendUrlChange,
}: BackendUrlSectionProps): JSX.Element {
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const handleTestConnection = async () => {
    if (!backendUrl.trim()) {
      setTestResult({
        success: false,
        message: "Please enter a backend URL first",
      });
      return;
    }

    setTestingConnection(true);
    setTestResult(null);

    try {
      // Construir URL para test de conexión
      const cleanedUrl = backendUrl.replace(/\/$/, "");
      const testUrl = `${cleanedUrl}/api/status`;

      const response = await fetch(testUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        setTestResult({
          success: true,
          message: "Connection successful!",
        });
      } else {
        setTestResult({
          success: false,
          message: `Connection failed: ${response.status} ${response.statusText}`,
        });
      }
    } catch (error) {
      setTestResult({
        success: false,
        message: `Connection error: ${error instanceof Error ? error.message : "Unknown error"}`,
      });
    } finally {
      setTestingConnection(false);
    }
  };

  return (
    <section className="settings-card">
      <h2>Backend Server URL</h2>
      <p>
        Configure the backend server URL to connect from remote devices (tablet, another PC, etc.).
        Leave empty to use the default local server.
      </p>
      <div className="setting-row">
        <div className="setting-info">
          <strong>Server URL</strong>
          <span>{backendUrl || "Default (localhost)"}</span>
        </div>
        <div className="setting-controls">
          <input
            type="text"
            value={backendUrl}
            onChange={(event) => onBackendUrlChange(event.target.value)}
            disabled={disabled}
            placeholder="http://192.168.1.100:8010"
          />
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={testingConnection || disabled || !backendUrl.trim()}
          >
            {testingConnection ? "Testing..." : "Test Connection"}
          </button>
        </div>
      </div>
      {testResult && (
        <div
          className={`connection-test-result ${testResult.success ? "success" : "error"}`}
          style={{
            marginTop: "0.5rem",
            padding: "0.5rem",
            borderRadius: "4px",
            backgroundColor: testResult.success ? "#d4edda" : "#f8d7da",
            color: testResult.success ? "#155724" : "#721c24",
            border: `1px solid ${testResult.success ? "#c3e6cb" : "#f5c6cb"}`,
          }}
        >
          {testResult.message}
        </div>
      )}
      <div
        className="setting-hint"
        style={{
          marginTop: "0.75rem",
          fontSize: "0.875rem",
          color: "#6c757d",
        }}
      >
        <strong>Examples:</strong>
        <ul style={{ marginTop: "0.25rem", paddingLeft: "1.25rem" }}>
          <li>Local: http://localhost:8010</li>
          <li>LAN: http://192.168.1.100:8010</li>
          <li>Remote: http://your-server.com:8010</li>
        </ul>
        <p style={{ marginTop: "0.5rem" }}>
          <strong>Note:</strong> Make sure the backend server is accessible from this device
          and CORS is properly configured if connecting from a different origin.
        </p>
      </div>
    </section>
  );
}
