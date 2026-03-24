"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Structured screen context that pages register to enrich AI queries.
 * The copilot panel and inline AI buttons consume this to send
 * the right project/entity/screen info to the backend.
 */
export interface AIScreenContext {
  screen: string;
  projectId?: number;
  disclosureId?: number;
  requirementItemId?: number;
  entityId?: number;
  dataPointId?: number;
  /** Any extra metadata a page wants to pass through. */
  extra?: Record<string, unknown>;
}

interface AIContextValue {
  /** Current registered screen context. */
  screenContext: AIScreenContext;
  /**
   * **Full reset** — called by the layout on route change.
   * Drops every field and sets only screen.
   * Pages should NOT use this.
   */
  resetScreenContext: (screen: string) => void;
  /**
   * **Enrich** — called by individual pages to add ids without
   * touching other fields set earlier in the same render cycle.
   * Does NOT reset — merges into the current context.
   */
  enrichScreenContext: (patch: Partial<Omit<AIScreenContext, "screen">>) => void;
  /** @deprecated Use resetScreenContext or enrichScreenContext instead. */
  setScreenContext: (ctx: Partial<AIScreenContext>) => void;
  /** Reset to default. */
  clearScreenContext: () => void;
}

const DEFAULT_CONTEXT: AIScreenContext = { screen: "unknown" };

const AIContext = createContext<AIContextValue>({
  screenContext: DEFAULT_CONTEXT,
  resetScreenContext: () => {},
  enrichScreenContext: () => {},
  setScreenContext: () => {},
  clearScreenContext: () => {},
});

export function AIContextProvider({ children }: { children: ReactNode }) {
  const [ctx, setCtx] = useState<AIScreenContext>(DEFAULT_CONTEXT);

  /** Layout calls this on every route change — wipes stale ids. */
  const resetScreenContext = useCallback(
    (screen: string) => setCtx({ screen }),
    [],
  );

  /** Pages call this to enrich (merge) ids into the current context. */
  const enrichScreenContext = useCallback(
    (patch: Partial<Omit<AIScreenContext, "screen">>) =>
      setCtx((prev) => ({ ...prev, ...patch })),
    [],
  );

  /** @deprecated — kept for backward compat. Behaves as reset. */
  const setScreenContext = useCallback(
    (partial: Partial<AIScreenContext>) =>
      setCtx({ screen: "unknown", ...partial }),
    [],
  );

  const clearScreenContext = useCallback(() => setCtx(DEFAULT_CONTEXT), []);

  const value = useMemo(
    () => ({
      screenContext: ctx,
      resetScreenContext,
      enrichScreenContext,
      setScreenContext,
      clearScreenContext,
    }),
    [ctx, resetScreenContext, enrichScreenContext, setScreenContext, clearScreenContext],
  );

  return <AIContext.Provider value={value}>{children}</AIContext.Provider>;
}

export function useAIScreenContext() {
  return useContext(AIContext);
}
