import { useEffect, useState, useCallback, type PropsWithChildren } from "react";
import { resolveBackendBaseUrl } from "../api/client";

// Import styles early - this component renders before App loads main styles
import "../styles/base.css";
import "../styles/startup.css";

type StartupState = "checking" | "waiting" | "connected" | "error";

interface BackendStartupGuardProps extends PropsWithChildren {
  /** Maximum time to wait for backend in ms (default: 30000) */
  timeout?: number;
  /** Interval between health checks in ms (default: 1000) */
  checkInterval?: number;
}

/**
 * Guards the application while the backend is starting up.
 * Shows a loading state until the backend health endpoint responds.
 */
export function BackendStartupGuard({
  children,
  timeout = 30000,
  checkInterval = 1000,
}: BackendStartupGuardProps): JSX.Element {
  const [state, setState] = useState<StartupState>("checking");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const checkHealth = useCallback(async (): Promise<boolean> => {
    try {
      const baseUrl = resolveBackendBaseUrl();
      const healthUrl = baseUrl
        ? `${baseUrl.endsWith("/api") ? baseUrl : `${baseUrl}/api`}/health`
        : "/api/health";

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(healthUrl, {
        method: "GET",
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        return data?.status === "ok";
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
    let intervalHandle: ReturnType<typeof setInterval> | null = null;
    const startTime = Date.now();

    const cleanup = () => {
      if (timeoutHandle) clearTimeout(timeoutHandle);
      if (intervalHandle) clearInterval(intervalHandle);
    };

    const performCheck = async () => {
      if (!mounted) return;

      const elapsed = Date.now() - startTime;

      // Check if we've exceeded the timeout
      if (elapsed >= timeout) {
        setState("error");
        setErrorMessage(
          "Unable to connect to backend server. Please check that the server is running."
        );
        cleanup();
        return;
      }

      const healthy = await checkHealth();

      if (!mounted) return;

      if (healthy) {
        setState("connected");
        cleanup();
      } else {
        setState("waiting");
      }
    };

    // Initial check
    performCheck();

    // Set up polling
    intervalHandle = setInterval(performCheck, checkInterval);

    // Global timeout
    timeoutHandle = setTimeout(() => {
      if (mounted && state !== "connected") {
        setState("error");
        setErrorMessage(
          "Connection timeout. The backend server did not respond in time."
        );
        cleanup();
      }
    }, timeout);

    return () => {
      mounted = false;
      cleanup();
    };
  }, [checkHealth, checkInterval, timeout, state]);

  // If connected, render children
  if (state === "connected") {
    return <>{children}</>;
  }

  return (
    <div className="startup-guard">
      <div className="startup-guard__content">
        <div className="startup-guard__logo">
          <svg
            viewBox="0 0 100 100"
            width="80"
            height="80"
            className="startup-guard__icon"
          >
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              opacity="0.2"
            />
            <circle
              cx="50"
              cy="50"
              r="35"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              opacity="0.4"
            />
            <circle
              cx="50"
              cy="50"
              r="25"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              opacity="0.6"
            />
            <circle cx="50" cy="50" r="8" fill="currentColor" />
          </svg>
        </div>

        <h1 className="startup-guard__title">AEGIS</h1>

        {state === "error" ? (
          <div className="startup-guard__error">
            <div className="startup-guard__error-icon">!</div>
            <p className="startup-guard__error-text">{errorMessage}</p>
            <button
              className="startup-guard__retry-btn"
              onClick={() => {
                setState("checking");
                setErrorMessage(null);
              }}
            >
              Retry Connection
            </button>
          </div>
        ) : (
          <div className="startup-guard__loading">
            <div className="startup-guard__spinner" />
            <p className="startup-guard__status">
              {state === "checking"
                ? "Connecting to backend..."
                : "Waiting for backend to start..."}
            </p>
            <p className="startup-guard__hint">
              This usually takes a few seconds while the server initializes.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
