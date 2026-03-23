"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, BotMessageSquare, Send, Sparkles, User, X } from "lucide-react";

import { api } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type AIStatus = {
  enabled: boolean;
  configured_provider: string;
  effective_provider: string;
  model: string;
  fallback_model: string;
  capabilities: string[];
};

type AIAction = {
  label: string;
  action_type: string;
  target: string;
  description?: string | null;
};

type AIReference = {
  title: string;
  source: string;
  url?: string | null;
};

type AIAnswer = {
  text: string;
  reasons?: string[] | null;
  next_actions?: AIAction[] | null;
  references?: AIReference[] | null;
  confidence: string;
  provider?: string | null;
};

type ChatMessage = {
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

interface AICopilotProps {
  open: boolean;
  onClose: () => void;
  screenContext?: string;
  entityType?: string;
  entityId?: string;
}

const quickPrompts = [
  "What should I check next?",
  "Explain the current workflow state",
  "What data is still missing?",
  "How should I interpret the boundary?",
];

export function AICopilot({
  open,
  onClose,
  screenContext,
  entityType,
  entityId,
}: AICopilotProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<AIStatus | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    void api
      .get<AIStatus>("/ai/status")
      .then(setStatus)
      .catch(() => setStatus(null));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 200);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const capabilitiesLabel = useMemo(() => status?.capabilities.join(", ") ?? "Unavailable", [status?.capabilities]);

  async function sendMessage(question: string) {
    if (!question.trim() || isLoading) return;
    setError("");
    const trimmed = question.trim();
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: trimmed },
    ]);
    setInput("");
    setIsLoading(true);
    try {
      const answer = await api.post<AIAnswer>("/ai/ask", {
        question: trimmed,
        screen: screenContext,
        context: {
          entity_type: entityType,
          entity_id: entityId,
        },
      });
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
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
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "AI temporarily unavailable.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <aside
      className={cn(
        "fixed right-0 top-0 z-40 flex h-full w-[420px] flex-col border-l border-slate-200 bg-white shadow-xl transition-transform duration-300 ease-in-out",
        open ? "translate-x-0" : "translate-x-full"
      )}
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <BotMessageSquare className="h-5 w-5 text-blue-600" />
            <h3 className="text-sm font-semibold text-slate-900">AI Copilot</h3>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Provider: {status?.effective_provider ?? "unknown"} · Capabilities: {capabilitiesLabel}
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close AI Copilot">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {error && (
        <div className="px-4 pt-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Sparkles className="mb-4 h-10 w-10 text-slate-300" />
            <p className="text-sm font-medium text-slate-700">Ask the backend AI assistant</p>
            <p className="mt-1 text-xs text-slate-500">Grounded answers only. No write actions are executed here.</p>
            <div className="mt-6 grid w-full gap-2">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => void sendMessage(prompt)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div key={message.id} className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cn("flex max-w-[88%] gap-2", message.role === "user" ? "flex-row-reverse" : "flex-row")}>
                  <div
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                      message.role === "user" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"
                    )}
                  >
                    {message.role === "user" ? <User className="h-3.5 w-3.5" /> : <BotMessageSquare className="h-3.5 w-3.5" />}
                  </div>
                  <div
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm",
                      message.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"
                    )}
                  >
                    <p>{message.content}</p>
                    {message.metadata?.provider && (
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                        <Badge variant="outline">{message.metadata.provider}</Badge>
                        {message.metadata.confidence ? <Badge variant="secondary">{message.metadata.confidence}</Badge> : null}
                      </div>
                    )}
                    {message.metadata?.reasons && message.metadata.reasons.length > 0 && (
                      <ul className="mt-3 list-disc space-y-1 pl-4 text-xs">
                        {message.metadata.reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    )}
                    {message.metadata?.nextActions && message.metadata.nextActions.length > 0 && (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs font-medium uppercase tracking-wide">Suggested actions</p>
                        {message.metadata.nextActions.map((action) => (
                          <div key={`${action.action_type}-${action.target}`} className="rounded-md border border-slate-200 bg-white/60 px-2 py-2 text-xs text-slate-700">
                            <p className="font-medium">{action.label}</p>
                            <p>{action.description ?? `${action.action_type} → ${action.target}`}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {message.metadata?.references && message.metadata.references.length > 0 && (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs font-medium uppercase tracking-wide">References</p>
                        {message.metadata.references.map((reference) => (
                          <div key={`${reference.source}-${reference.title}`} className="text-xs text-slate-700">
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
            {isLoading && (
              <div className="flex justify-start">
                <div className="flex max-w-[88%] gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                    <BotMessageSquare className="h-3.5 w-3.5" />
                  </div>
                  <div className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600">Thinking…</div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 px-4 py-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage(input);
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
          <Button type="submit" size="icon" disabled={isLoading || !input.trim()} aria-label="Send AI message">
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </aside>
  );
}
