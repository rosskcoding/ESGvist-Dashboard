"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import {
  X,
  Send,
  BotMessageSquare,
  User,
  AlertCircle,
  Sparkles,
} from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface AICopilotProps {
  open: boolean;
  onClose: () => void;
  screenContext?: string;
  entityType?: string;
  entityId?: string;
}

const quickPrompts = [
  "Explain this metric",
  "What data is missing?",
  "Help me understand boundary",
  "Suggest next steps",
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
  const [isStreaming, setIsStreaming] = useState(false);
  const [serviceDown, setServiceDown] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [open]);

  const sendMessage = async (question: string) => {
    if (!question.trim() || isStreaming) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsStreaming(true);
    setServiceDown(false);

    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", timestamp: new Date() },
    ]);

    try {
      const token = localStorage.getItem("access_token");
      const orgId = localStorage.getItem("organization_id");

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (orgId) headers["X-Organization-Id"] = orgId;

      const response = await fetch("/api/ai/ask", {
        method: "POST",
        headers,
        body: JSON.stringify({
          question: question.trim(),
          screen_context: screenContext ?? "",
          entity_type: entityType ?? "",
          entity_id: entityId ?? "",
        }),
      });

      if (!response.ok) {
        throw new Error("AI service unavailable");
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response stream");
      }

      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, content: accumulated } : msg
          )
        );
      }
    } catch {
      setServiceDown(true);
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <aside
      className={cn(
        "fixed right-0 top-0 z-40 flex h-full w-[400px] flex-col border-l border-slate-200 bg-white shadow-xl transition-transform duration-300 ease-in-out",
        open ? "translate-x-0" : "translate-x-full"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <BotMessageSquare className="h-5 w-5 text-blue-600" />
          <h3 className="text-sm font-semibold text-slate-900">AI Assistant</h3>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-8 w-8 text-slate-400 hover:text-slate-600"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Service Down Alert */}
      {serviceDown && (
        <div className="px-4 pt-3">
          <Alert variant="warning">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              AI temporarily unavailable. Please try again later.
            </AlertDescription>
          </Alert>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center">
            <Sparkles className="mb-4 h-10 w-10 text-slate-300" />
            <p className="mb-1 text-sm font-medium text-slate-600">
              How can I help?
            </p>
            <p className="mb-6 text-xs text-slate-400">
              Ask questions about your ESG reporting
            </p>
            <div className="w-full space-y-2">
              <p className="text-xs font-medium text-slate-500">Quick prompts</p>
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex",
                  msg.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                <div
                  className={cn(
                    "flex max-w-[85%] gap-2",
                    msg.role === "user" ? "flex-row-reverse" : "flex-row"
                  )}
                >
                  <div
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                      msg.role === "user"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-slate-100 text-slate-600"
                    )}
                  >
                    {msg.role === "user" ? (
                      <User className="h-3 w-3" />
                    ) : (
                      <BotMessageSquare className="h-3 w-3" />
                    )}
                  </div>
                  <div
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm",
                      msg.role === "user"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-100 text-slate-800"
                    )}
                  >
                    {msg.content || (
                      <span className="inline-flex items-center gap-1">
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-slate-200 px-4 py-3">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the AI assistant..."
            disabled={isStreaming}
            className="flex-1"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isStreaming}
            className="shrink-0"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </aside>
  );
}
