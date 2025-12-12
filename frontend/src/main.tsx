import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import { BackendStartupGuard } from "./components/BackendStartupGuard";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5_000,
    },
  },
});

// Note: StrictMode disabled temporarily to fix WebSocket connection issues
// StrictMode causes double-mount in development which closes WebSocket before connection completes
// This is not an issue in production builds where StrictMode effects don't apply
createRoot(document.getElementById("root")!).render(
  <BackendStartupGuard timeout={30000} checkInterval={1000}>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </BackendStartupGuard>
);
