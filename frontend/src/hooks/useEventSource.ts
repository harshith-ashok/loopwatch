import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { apiUrl } from "../lib/api";

export const EVENT_TYPES = [
  "heartbeat",
  "journey.updated",
  "incident.opened",
  "incident.updated",
  "approval.requested",
  "edge.telemetry",
  "audit.appended",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

export interface ServerEvent {
  type: EventType;
  ts: string;
  data: Record<string, unknown>;
}

// Which cached queries each event makes stale.
const INVALIDATES: Partial<Record<EventType, string[]>> = {
  "journey.updated": ["journeys", "overview"],
  "incident.opened": ["incidents", "overview"],
  "incident.updated": ["incidents", "overview"],
  "approval.requested": ["incidents", "overview"],
  "edge.telemetry": ["edge"],
  "audit.appended": ["audit"],
};

export type ConnectionState = "connecting" | "open" | "closed";

/** Connects to GET /api/v1/events and keeps the TanStack Query cache fresh. */
export function useEventSource(onEvent?: (event: ServerEvent) => void): ConnectionState {
  const queryClient = useQueryClient();
  const [state, setState] = useState<ConnectionState>("connecting");
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  });

  useEffect(() => {
    const source = new EventSource(apiUrl("/events"));
    source.onopen = () => setState("open");
    source.onerror = () => setState(source.readyState === EventSource.CLOSED ? "closed" : "connecting");

    const handlers = EVENT_TYPES.map((type) => {
      const handler = (msg: MessageEvent<string>) => {
        const event = JSON.parse(msg.data) as ServerEvent;
        queryClient.setQueryData(["event", type], event);
        onEventRef.current?.(event);
        if (type === "heartbeat") {
          queryClient.setQueryData<ServerEvent[]>(["heartbeats"], (old = []) => [event, ...old].slice(0, 20));
        }
        for (const key of INVALIDATES[type] ?? []) {
          void queryClient.invalidateQueries({ queryKey: [key] });
        }
      };
      source.addEventListener(type, handler as EventListener);
      return [type, handler] as const;
    });

    return () => {
      for (const [type, handler] of handlers) source.removeEventListener(type, handler as EventListener);
      source.close();
    };
  }, [queryClient]);

  return state;
}
