import { create } from "zustand";

/**
 * Estado del store de conexión al backend.
 *
 * Tracks:
 *   - isConnected: Si el backend está respondiendo
 *   - lastConnectedAt: Timestamp de última conexión exitosa
 *   - connectionAttempts: Número de intentos de conexión fallidos consecutivos
 */
interface ConnectionState {
  isConnected: boolean;
  lastConnectedAt: number | null;
  connectionAttempts: number;
  setConnected: (connected: boolean) => void;
  incrementAttempts: () => void;
  resetAttempts: () => void;
}

/**
 * Store global para el estado de conexión al backend.
 *
 * Se usa para:
 * - Detectar cuando el backend pasa de offline a online
 * - Triggear refetch de queries fallidas
 * - Mostrar indicadores de conexión en la UI
 */
export const useConnectionStore = create<ConnectionState>((set, get) => ({
  isConnected: false,
  lastConnectedAt: null,
  connectionAttempts: 0,

  setConnected: (connected: boolean) => {
    const wasConnected = get().isConnected;
    const now = Date.now();

    set({
      isConnected: connected,
      lastConnectedAt: connected ? now : get().lastConnectedAt,
      connectionAttempts: connected ? 0 : get().connectionAttempts,
    });

    // Emit custom event when transitioning from disconnected to connected
    if (!wasConnected && connected) {
      window.dispatchEvent(new CustomEvent("backend-connected", { detail: { timestamp: now } }));
    }
  },

  incrementAttempts: () => {
    set((state) => ({ connectionAttempts: state.connectionAttempts + 1 }));
  },

  resetAttempts: () => {
    set({ connectionAttempts: 0 });
  },
}));
