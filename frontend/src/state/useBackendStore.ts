import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Estado del store de backend URL.
 *
 * Attributes:
 *     backendUrl: URL del servidor backend configurada (null = usar default)
 *     setBackendUrl: Actualiza la URL del backend
 */
interface BackendState {
  backendUrl: string | null;
  setBackendUrl: (url: string | null) => void;
}

const STORAGE_KEY = "code-map-backend-url";

/**
 * Store global para la URL del servidor backend (Zustand + persist).
 *
 * Mantiene la URL del backend configurada por el usuario. Se persiste
 * en localStorage para sobrevivir recargas del navegador.
 *
 * Returns:
 *     Hook con estado y acciones del store
 *
 * Usage:
 *     const { backendUrl, setBackendUrl } = useBackendStore();
 *     setBackendUrl("http://192.168.1.100:8010");
 *
 * Notes:
 *     - Store singleton (compartido por todos los componentes)
 *     - Persiste en localStorage automáticamente
 *     - null significa usar la URL por defecto (env var o /api)
 *     - Se sincroniza con la configuración del servidor
 */
export const useBackendStore = create<BackendState>()(
  persist(
    (set) => ({
      backendUrl: null,

      /**
       * Actualiza la URL del servidor backend.
       *
       * Args:
       *     url: Nueva URL del backend (null para resetear a default)
       *
       * Notes:
       *     - Acepta URLs completas: http://host:port
       *     - null resetea a comportamiento por defecto
       *     - Se persiste automáticamente en localStorage
       *     - Debe incluir protocolo (http:// o https://)
       */
      setBackendUrl(url) {
        set({ backendUrl: url });
      },
    }),
    {
      name: STORAGE_KEY,
    }
  )
);
