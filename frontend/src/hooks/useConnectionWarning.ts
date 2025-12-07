/**
 * Hook to warn users when navigating away from a page with an active connection.
 *
 * Handles:
 * 1. Browser tab close / reload (beforeunload event)
 * 2. Internal navigation via link clicks (captures click events)
 *
 * Note: Works with BrowserRouter (doesn't require data router).
 */

import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

interface UseConnectionWarningOptions {
  /** Whether there's an active connection that would be lost */
  isConnected: boolean;
  /** Custom warning message (optional) */
  message?: string;
}

const DEFAULT_MESSAGE =
  "You have an active terminal connection. Leaving this page will disconnect the session. Are you sure you want to leave?";

/**
 * Warns users before navigating away from pages with active connections.
 *
 * @example
 * ```tsx
 * function TerminalPage() {
 *   const [connected, setConnected] = useState(false);
 *   useConnectionWarning({ isConnected: connected });
 *   // ...
 * }
 * ```
 */
export function useConnectionWarning({
  isConnected,
  message = DEFAULT_MESSAGE,
}: UseConnectionWarningOptions): void {
  const location = useLocation();
  const navigate = useNavigate();

  // Intercept link clicks to show confirmation before navigation
  useEffect(() => {
    if (!isConnected) return;

    const handleClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      const anchor = target.closest("a");

      if (!anchor) return;

      const href = anchor.getAttribute("href");
      if (!href) return;

      // Only intercept internal navigation (same origin, different path)
      try {
        const url = new URL(href, window.location.origin);

        // Skip external links
        if (url.origin !== window.location.origin) return;

        // Skip same-page navigation
        if (url.pathname === location.pathname) return;

        // Show confirmation
        event.preventDefault();
        event.stopPropagation();

        const confirmed = window.confirm(message);
        if (confirmed) {
          navigate(url.pathname + url.search + url.hash);
        }
      } catch {
        // Invalid URL, let browser handle it
        return;
      }
    };

    // Capture phase to intercept before React Router
    document.addEventListener("click", handleClick, true);

    return () => {
      document.removeEventListener("click", handleClick, true);
    };
  }, [isConnected, location.pathname, message, navigate]);

  // Handle browser close/reload (beforeunload)
  useEffect(() => {
    if (!isConnected) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      // Standard way to trigger browser's native "Leave site?" dialog
      event.preventDefault();
      // For older browsers
      event.returnValue = message;
      return message;
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isConnected, message]);
}
