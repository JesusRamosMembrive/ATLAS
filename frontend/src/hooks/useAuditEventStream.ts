import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "../api/queryKeys";
import type { AuditEvent } from "../api/types";
import { useBackendStore } from "../state/useBackendStore";

/**
 * Hook para manejar el stream de eventos SSE de audit trail.
 *
 * Establece y mantiene una conexión EventSource para recibir eventos
 * de audit en tiempo real desde el servidor. Invalida queries de React Query
 * automáticamente cuando llegan nuevos eventos.
 *
 * Args:
 *     runId: ID del audit run a monitorear. Si es null, no se conecta.
 *     enabled: Si false, no establece la conexión SSE.
 *
 * Returns:
 *     - events: Array de eventos recibidos en tiempo real
 *     - isConnected: Estado de la conexión SSE
 *     - error: Mensaje de error si la conexión falla
 *
 * Side Effects:
 *     - Invalida queryKeys.auditEvents(runId) cuando llega un nuevo evento
 *     - Invalida queryKeys.auditRun(runId) para actualizar event_count
 *     - Reconecta automáticamente en caso de error
 *
 * Usage:
 *     const { events, isConnected } = useAuditEventStream(runId);
 */
export function useAuditEventStream(
  runId: number | null,
  enabled: boolean = true
): {
  events: AuditEvent[];
  isConnected: boolean;
  error: string | null;
} {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // No conectar si no hay runId o está deshabilitado
    if (!runId || !enabled) {
      setIsConnected(false);
      return;
    }

    // Build SSE URL using same logic as API client
    const backendUrl = useBackendStore.getState().backendUrl || "http://localhost:8010";
    const baseUrl = backendUrl.endsWith("/api") ? backendUrl : `${backendUrl}/api`;
    const url = `${baseUrl}/audit/runs/${runId}/stream`;
    const eventSource = new EventSource(url);

    const handleOpen = () => {
      setIsConnected(true);
      setError(null);
      console.log(`[Audit SSE] Connected to run ${runId}`);
    };

    const handleAuditEvent = (event: MessageEvent<string>) => {
      try {
        const auditEvent = JSON.parse(event.data) as AuditEvent;

        // Añadir evento al estado local
        setEvents((prev) => [...prev, auditEvent]);

        // Invalidar queries para actualizar la UI
        queryClient.invalidateQueries({
          queryKey: queryKeys.auditEvents(runId)
        });
        queryClient.invalidateQueries({
          queryKey: queryKeys.auditRun(runId)
        });

        console.log(`[Audit SSE] Event received:`, auditEvent.type, auditEvent.title);
      } catch (err) {
        console.warn("[Audit SSE] Failed to parse audit event", err);
      }
    };

    const handleError = (err: Event) => {
      console.warn(`[Audit SSE] Connection error for run ${runId}`, err);
      setIsConnected(false);
      setError("Connection lost, retrying...");
    };

    // Registrar listeners
    eventSource.addEventListener("open", handleOpen);
    eventSource.addEventListener("audit_event", handleAuditEvent as EventListener);
    eventSource.addEventListener("error", handleError);

    // Cleanup
    return () => {
      console.log(`[Audit SSE] Disconnecting from run ${runId}`);
      eventSource.removeEventListener("open", handleOpen);
      eventSource.removeEventListener("audit_event", handleAuditEvent as EventListener);
      eventSource.removeEventListener("error", handleError);
      eventSource.close();
      setIsConnected(false);
      setEvents([]);
    };
  }, [runId, enabled, queryClient]);

  return { events, isConnected, error };
}
