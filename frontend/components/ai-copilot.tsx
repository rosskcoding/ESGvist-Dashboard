"use client";

import { useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, BotMessageSquare, Send, Sparkles, StopCircle, User, X } from "lucide-react";

import { useAICopilot, type AIAction } from "@/lib/hooks/use-ai-copilot";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface AICopilotProps {
  open: boolean;
  onClose: () => void;
}

const quickPrompts = [
  "What should I check next?",
  "Explain the current workflow state",
  "What data is still missing?",
  "How should I interpret the boundary?",
];

export function AICopilot({ open, onClose }: AICopilotProps) {
  const router = useRouter();
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    isLoading,
    isStreaming,
    error,
    status,
    fetchStatus,
    sendMessageStream,
    cancelStream,
    executeAction,
    screenContext,
  } = useAICopilot({
    onNavigate: (path) => router.push(path),
    onOpenDialog: (target) => {
      // Dialog registry: emit custom event for the target dialog
      window.dispatchEvent(
        new CustomEvent("ai:open-dialog", { detail: { target } }),
      );
    },
    onHighlight: (target) => {
      // Highlight registry: emit custom event
      window.dispatchEvent(
        new CustomEvent("ai:highlight", { detail: { target } }),
      );
    },
  });

  useEffect(() => {
    if (open) void fetchStatus();
  }, [open, fetchStatus]);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 200);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const capabilitiesLabel = useMemo(
    () => status?.capabilities.join(", ") ?? "Unavailable",
    [status?.capabilities],
  );

  function handleSubmit(question: string) {
    if (!question.trim()) return;
    setInput("");
    void sendMessageStream(question);
  }

  function handleActionClick(action: AIAction) {
    executeAction(action);
  }

  return (
    <aside
      className={cn(
        "fixed right-0 top-0 z-40 flex h-full w-[420px] flex-col border-l border-slate-200 bg-white shadow-xl transition-transform duration-300 ease-in-out",
        open ? "translate-x-0" : "translate-x-full",
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <BotMessageSquare className="h-5 w-5 text-cyan-600" />
            <h3 className="text-sm font-semibold text-slate-900">AI Copilot</h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Provider: {status?.effective_provider ?? "unknown"} · Capabilities:{" "}
            {capabilitiesLabel}
          </p>
          {screenContext.screen !== "unknown" && (
            <p className="text-xs text-cyan-500">
              Context: {screenContext.screen}
              {screenContext.projectId ? ` · Project #${screenContext.projectId}` : ""}
            </p>
          )}
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close AI Copilot">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 pt-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Sparkles className="mb-4 h-10 w-10 text-slate-300" />
            <p className="text-sm font-medium text-slate-700">
              Ask the backend AI assistant
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Grounded answers only. No write actions are executed here.
            </p>
            <div className="mt-6 grid w-full gap-2">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSubmit(prompt)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-600 transition-colors hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex",
                  message.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                <div
                  className={cn(
                    "flex max-w-[88%] gap-2",
                    message.role === "user" ? "flex-row-reverse" : "flex-row",
                  )}
                >
                  <div
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                      message.role === "user"
                        ? "bg-cyan-100 text-cyan-700"
                        : "bg-slate-100 text-slate-600",
                    )}
                  >
                    {message.role === "user" ? (
                      <User className="h-3.5 w-3.5" />
                    ) : (
                      <BotMessageSquare className="h-3.5 w-3.5" />
                    )}
                  </div>
                  <div
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm",
                      message.role === "user"
                        ? "bg-cyan-600 text-white"
                        : "bg-slate-100 text-slate-800",
                    )}
                  >
                    <p>{message.content}</p>

                    {/* Provider & confidence badges */}
                    {message.metadata?.provider && (
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                        <Badge variant="outline">{message.metadata.provider}</Badge>
                        {message.metadata.confidence ? (
                          <Badge variant="secondary">{message.metadata.confidence}</Badge>
                        ) : null}
                      </div>
                    )}

                    {/* Reasons */}
                    {message.metadata?.reasons && message.metadata.reasons.length > 0 && (
                      <ul className="mt-3 list-disc space-y-1 pl-4 text-xs">
                        {message.metadata.reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    )}

                    {/* Suggested actions — now interactive */}
                    {message.metadata?.nextActions &&
                      message.metadata.nextActions.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-xs font-medium uppercase tracking-wide">
                            Suggested actions
                          </p>
                          {message.metadata.nextActions.map((action) => (
                            <button
                              key={`${action.action_type}-${action.target}`}
                              type="button"
                              onClick={() => handleActionClick(action)}
                              className="w-full rounded-md border border-slate-200 bg-white/60 px-2 py-2 text-left text-xs text-slate-700 transition-colors hover:border-cyan-300 hover:bg-cyan-50"
                            >
                              <p className="font-medium">{action.label}</p>
                              <p>
                                {action.description ??
                                  `${action.action_type} → ${action.target}`}
                              </p>
                            </button>
                          ))}
                        </div>
                      )}

                    {/* References */}
                    {message.metadata?.references &&
                      message.metadata.references.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-xs font-medium uppercase tracking-wide">
                            References
                          </p>
                          {message.metadata.references.map((reference) => (
                            <div
                              key={`${reference.source}-${reference.title}`}
                              className="text-xs text-slate-700"
                            >
                              <p className="font-medium">{reference.title}</p>
                              <p>{reference.source}</p>
                            </div>
                          ))}
                        </div>
                      )}
                  </div>
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {isLoading && !isStreaming && (
              <div className="flex justify-start">
                <div className="flex max-w-[88%] gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                    <BotMessageSquare className="h-3.5 w-3.5" />
                  </div>
                  <div className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600">
                    Thinking...
                  </div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 px-4 py-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            handleSubmit(input);
          }}
          className="flex items-center gap-2"
        >
          <Input
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask the AI copilot..."
            disabled={isLoading}
          />
          {isStreaming ? (
            <Button
              type="button"
              size="icon"
              variant="destructive"
              onClick={cancelStream}
              aria-label="Stop streaming"
            >
              <StopCircle className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon"
              disabled={isLoading || !input.trim()}
              aria-label="Send AI message"
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </form>
      </div>
    </aside>
  );
}
