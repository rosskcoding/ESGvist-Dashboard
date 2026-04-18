"use client";

import { useState } from "react";
import { HelpCircle, Loader2, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────

type AIExplainResponse = {
  text: string;
  reasons?: string[] | null;
  next_actions?: Array<{
    label: string;
    action_type: string;
    target: string;
    description?: string | null;
  }> | null;
  references?: Array<{
    title: string;
    source: string;
  }> | null;
  confidence: string;
  provider?: string | null;
};

// ── Field Explain Button (inline ?) ────────────────────────────────────

interface AIFieldExplainProps {
  requirementItemId: number;
  className?: string;
}

export function AIFieldExplain({ requirementItemId, className }: AIFieldExplainProps) {
  const [response, setResponse] = useState<AIExplainResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");

  async function handleClick() {
    if (response) {
      setIsOpen(!isOpen);
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const data = await api.post<AIExplainResponse>("/ai/explain/field", {
        requirement_item_id: requirementItemId,
      });
      setResponse(data);
      setIsOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to explain field");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <span className={cn("inline-flex flex-col", className)}>
      <button
        type="button"
        onClick={handleClick}
        disabled={isLoading}
        className="inline-flex items-center gap-1 text-slate-400 transition-colors hover:text-cyan-600"
        title="Explain this field with AI"
        aria-label="Explain field"
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <HelpCircle className="h-3.5 w-3.5" />
        )}
      </button>
      {error && <span className="mt-1 text-xs text-red-500">{error}</span>}
      {isOpen && response && (
        <AIExplainTooltip response={response} onClose={() => setIsOpen(false)} />
      )}
    </span>
  );
}

// ── Boundary "Why?" Link ───────────────────────────────────────────────

interface AIBoundaryWhyProps {
  entityId: number;
  projectId?: number;
  included: boolean;
  className?: string;
}

export function AIBoundaryWhy({ entityId, projectId, included, className }: AIBoundaryWhyProps) {
  const [response, setResponse] = useState<AIExplainResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");

  async function handleClick() {
    if (response) {
      setIsOpen(!isOpen);
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const data = await api.post<AIExplainResponse>("/ai/explain/boundary", {
        entity_id: entityId,
        project_id: projectId,
      });
      setResponse(data);
      setIsOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to explain boundary");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <span className={cn("inline-flex flex-col", className)}>
      <button
        type="button"
        onClick={handleClick}
        disabled={isLoading}
        className="inline-flex items-center gap-1 text-xs text-cyan-600 underline-offset-2 transition-colors hover:text-cyan-800 hover:underline"
        title="Explain boundary decision"
      >
        {isLoading ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <>Why {included ? "included" : "excluded"}?</>
        )}
      </button>
      {error && <span className="mt-1 text-xs text-red-500">{error}</span>}
      {isOpen && response && (
        <AIExplainTooltip response={response} onClose={() => setIsOpen(false)} />
      )}
    </span>
  );
}

// ── Evidence Guidance Card ─────────────────────────────────────────────

interface AIEvidenceGuidanceProps {
  requirementItemId: number;
  className?: string;
}

export function AIEvidenceGuidance({ requirementItemId, className }: AIEvidenceGuidanceProps) {
  const [response, setResponse] = useState<AIExplainResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");

  async function handleClick() {
    if (response) {
      setIsOpen(!isOpen);
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const data = await api.post<AIExplainResponse>("/ai/explain/evidence", {
        requirement_item_id: requirementItemId,
      });
      setResponse(data);
      setIsOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get evidence guidance");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className={cn("", className)}>
      <Button
        variant="outline"
        size="sm"
        onClick={handleClick}
        disabled={isLoading}
        className="gap-1.5"
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <HelpCircle className="h-3.5 w-3.5" />
        )}
        Evidence guidance
      </Button>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      {isOpen && response && (
        <AIExplainCard response={response} onClose={() => setIsOpen(false)} />
      )}
    </div>
  );
}

// ── Completeness "Why partial?" per-disclosure ─────────────────────────

interface AICompletenessWhyProps {
  projectId: number;
  disclosureId?: number;
  status: string;
  className?: string;
}

export function AICompletenessWhy({
  projectId,
  disclosureId,
  status,
  className,
}: AICompletenessWhyProps) {
  const [response, setResponse] = useState<AIExplainResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");

  if (status === "complete" || status === "not_applicable") return null;

  async function handleClick() {
    if (response) {
      setIsOpen(!isOpen);
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const data = await api.post<AIExplainResponse>("/ai/explain/completeness", {
        project_id: projectId,
        disclosure_id: disclosureId,
      });
      setResponse(data);
      setIsOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to explain completeness");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <span className={cn("inline-flex flex-col", className)}>
      <button
        type="button"
        onClick={handleClick}
        disabled={isLoading}
        className="inline-flex items-center gap-1 text-xs text-amber-600 underline-offset-2 transition-colors hover:text-amber-800 hover:underline"
        title="Explain completeness status"
      >
        {isLoading ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <>Why {status}?</>
        )}
      </button>
      {error && <span className="mt-1 text-xs text-red-500">{error}</span>}
      {isOpen && response && (
        <AIExplainTooltip response={response} onClose={() => setIsOpen(false)} />
      )}
    </span>
  );
}

// ── Shared Tooltip ─────────────────────────────────────────────────────

function AIExplainTooltip({
  response,
  onClose,
}: {
  response: AIExplainResponse;
  onClose: () => void;
}) {
  return (
    <div className="mt-2 max-w-sm rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-slate-800">{response.text}</p>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 text-slate-400 hover:text-slate-600"
          aria-label="Close"
        >
          <ChevronUp className="h-4 w-4" />
        </button>
      </div>
      {response.reasons && response.reasons.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-slate-600">
          {response.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {response.confidence && (
        <div className="mt-2">
          <Badge variant="secondary" className="text-xs">
            {response.confidence}
          </Badge>
        </div>
      )}
    </div>
  );
}

// ── Shared Card (for larger inline explanations) ───────────────────────

function AIExplainCard({
  response,
  onClose,
}: {
  response: AIExplainResponse;
  onClose: () => void;
}) {
  return (
    <div className="mt-3 rounded-lg border border-cyan-100 bg-cyan-50/50 p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-slate-800">{response.text}</p>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 text-slate-400 hover:text-slate-600"
          aria-label="Close"
        >
          <ChevronUp className="h-4 w-4" />
        </button>
      </div>
      {response.reasons && response.reasons.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-600">
          {response.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {response.references && response.references.length > 0 && (
        <div className="mt-3 border-t border-cyan-100 pt-2">
          <p className="text-xs font-medium text-slate-500">References</p>
          {response.references.map((ref) => (
            <p key={`${ref.source}-${ref.title}`} className="text-xs text-slate-600">
              {ref.title} ({ref.source})
            </p>
          ))}
        </div>
      )}
      {response.next_actions && response.next_actions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {response.next_actions.map((action) => (
            <Badge
              key={`${action.action_type}-${action.target}`}
              variant="outline"
              className="cursor-default text-xs"
            >
              {action.label}
            </Badge>
          ))}
        </div>
      )}
      <div className="mt-2">
        <Badge variant="secondary" className="text-xs">
          {response.confidence} confidence
        </Badge>
        {response.provider && (
          <Badge variant="outline" className="ml-1 text-xs">
            {response.provider}
          </Badge>
        )}
      </div>
    </div>
  );
}
