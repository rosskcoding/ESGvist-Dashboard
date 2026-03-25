"use client";

import { useCallback, useRef, useState } from "react";
import { api, isAppApiError } from "@/lib/api";
import { useAIScreenContext, type AIScreenContext } from "@/lib/ai-context";

// ── Types ──────────────────────────────────────────────────────────────

export type AIAction = {
  label: string;
  action_type: string;
  target: string;
  description?: string | null;
};

export type AIReference = {
  title: string;
  source: string;
  url?: string | null;
};

export type AIAnswer = {
  text: string;
  reasons?: string[] | null;
  next_actions?: AIAction[] | null;
  references?: AIReference[] | null;
  confidence: string;
  provider?: string | null;
};

export type AIStatus = {
  enabled: boolean;
  configured_provider: string;
  effective_provider: string;
  model: string;
  fallback_model: string;
  capabilities: string[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: {
    reasons?: string[];
    nextActions?: AIAction[];
    references?: AIReference[];
    provider?: string | null;
    confidence?: string;
  };
};

// ── Allowed action targets (allowlist) ─────────────────────────────────

const ALLOWED_NAVIGATE_TARGETS = new Set([
  "/dashboard",
  "/collection",
  "/evidence",
  "/evidence/upload",
  "/validation",
  "/merge",
  "/completeness",
  "/report",
  "/requirements",
  "/settings/boundaries",
  "/settings/company-structure",
  "/settings/assignments",
  "/settings/standards",
  "/settings/shared-elements",
  "/boundary_view",
]);

function isAllowedTarget(target: string): boolean {
  // Allow exact matches
  if (ALLOWED_NAVIGATE_TARGETS.has(target)) return true;
  // Allow targets that start with known prefixes + /
  for (const allowed of ALLOWED_NAVIGATE_TARGETS) {
    if (target.startsWith(allowed + "/")) return true;
  }
  return false;
}

// ── Hook ───────────────────────────────────────────────────────────────

export interface UseAICopilotOptions {
  onNavigate?: (path: string) => void;
  onOpenDialog?: (target: string) => void;
  onHighlight?: (target: string) => void;
}

export function useAICopilot(options: UseAICopilotOptions = {}) {
  const { screenContext } = useAIScreenContext();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.get<AIStatus>("/ai/status");
      setStatus(s);
    } catch {
      setStatus(null);
    }
  }, []);

  const buildRequestContext = useCallback(
    (ctx: AIScreenContext) => {
      const context: Record<string, unknown> = {};
      if (ctx.projectId) context.project_id = ctx.projectId;
      if (ctx.disclosureId) context.disclosure_id = ctx.disclosureId;
      if (ctx.requirementItemId) context.requirement_item_id = ctx.requirementItemId;
      if (ctx.entityId) context.entity_id = ctx.entityId;
      if (ctx.dataPointId) context.data_point_id = ctx.dataPointId;
      if (ctx.extra) Object.assign(context, ctx.extra);
      return context;
    },
    [],
  );

  // ── Regular (non-streaming) ask ────────────────────────────────────

  const sendMessage = useCallback(
    async (question: string) => {
      if (!question.trim() || isLoading) return;
      setError("");
      const trimmed = question.trim();
      setMessages((prev) => [
        ...prev,
        { id: `user-${crypto.randomUUID()}`, role: "user", content: trimmed },
      ]);
      setIsLoading(true);
      try {
        const answer = await api.post<AIAnswer>("/ai/ask", {
          question: trimmed,
          screen: screenContext.screen,
          context: buildRequestContext(screenContext),
        });
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-${crypto.randomUUID()}`,
            role: "assistant",
            content: answer.text,
            metadata: {
              reasons: answer.reasons ?? undefined,
              nextActions: answer.next_actions ?? undefined,
              references: answer.references ?? undefined,
              provider: answer.provider,
              confidence: answer.confidence,
            },
          },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "AI temporarily unavailable.");
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, screenContext, buildRequestContext],
  );

  // ── Streaming ask ──────────────────────────────────────────────────

  const sendMessageStream = useCallback(
    async (question: string) => {
      if (!question.trim() || isLoading || isStreaming) return;
      setError("");
      const trimmed = question.trim();
      setMessages((prev) => [
        ...prev,
        { id: `user-${crypto.randomUUID()}`, role: "user", content: trimmed },
      ]);
      setIsStreaming(true);
      setIsLoading(true);

      const assistantId = `assistant-${crypto.randomUUID()}`;
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "" },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await api.stream(
          "/ai/ask/stream",
          {
            question: trimmed,
            screen: screenContext.screen,
            context: buildRequestContext(screenContext),
          },
          {
            signal: controller.signal,
          },
        );

        if (!response.body) {
          throw new Error("AI stream response body is missing");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const event = JSON.parse(line);
              if (event.type === "chunk") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + event.text }
                      : m,
                  ),
                );
              } else if (event.type === "done" && event.response) {
                const resp = event.response as AIAnswer;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? {
                          ...m,
                          content: resp.text,
                          metadata: {
                            reasons: resp.reasons ?? undefined,
                            nextActions: resp.next_actions ?? undefined,
                            references: resp.references ?? undefined,
                            provider: resp.provider,
                            confidence: resp.confidence,
                          },
                        }
                      : m,
                  ),
                );
              } else if (event.type === "error") {
                setError(event.message || "Stream error");
              }
            } catch {
              // skip malformed lines
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError(
            isAppApiError(err)
              ? err.message
              : err instanceof Error
                ? err.message
                : "Stream failed",
          );
        }
      } finally {
        setIsStreaming(false);
        setIsLoading(false);
        abortRef.current = null;
      }
    },
    [isLoading, isStreaming, screenContext, buildRequestContext],
  );

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  // ── Action handler ─────────────────────────────────────────────────

  const executeAction = useCallback(
    (action: AIAction) => {
      const target = action.target;
      if (!isAllowedTarget(target)) {
        console.warn(`AI suggested action target "${target}" is not allowlisted.`);
        return;
      }

      switch (action.action_type) {
        case "navigate":
          options.onNavigate?.(target);
          break;
        case "open_dialog":
          options.onOpenDialog?.(target);
          break;
        case "highlight":
          options.onHighlight?.(target);
          break;
        default:
          console.warn(`Unknown AI action type: ${action.action_type}`);
      }
    },
    [options],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError("");
  }, []);

  return {
    messages,
    isLoading,
    isStreaming,
    error,
    status,
    fetchStatus,
    sendMessage,
    sendMessageStream,
    cancelStream,
    executeAction,
    clearMessages,
    screenContext,
  };
}
