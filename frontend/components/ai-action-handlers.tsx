"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

const DIALOG_MAP: Record<string, { title: string; description: string }> = {
  "/evidence/upload": {
    title: "Upload Evidence",
    description: "Navigate to the evidence page to attach supporting documents to your data points.",
  },
  "/requirements": {
    title: "Requirement Details",
    description: "View the full requirement definition including field type, standard reference, and evidence rules.",
  },
};

/**
 * Global listener for AI-suggested action events.
 *
 * Handles:
 *  - `ai:open-dialog`  — opens a dialog or navigates if no dialog is mapped
 *  - `ai:highlight`    — scrolls to & briefly highlights a DOM element
 *
 * Mount this once in the app layout.
 */
export function AIActionHandlers() {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogInfo, setDialogInfo] = useState<{ title: string; description: string; target: string } | null>(null);

  // ── Dialog mapping ─────────────────────────────────────────────────
  const handleOpenDialog = useCallback(
    (event: Event) => {
      const target = (event as CustomEvent<{ target: string }>).detail?.target;
      if (!target) return;

      const mapped = DIALOG_MAP[target];
      if (mapped) {
        setDialogInfo({ ...mapped, target });
        setDialogOpen(true);
      } else {
        // Fallback: navigate to the target
        router.push(target);
      }
    },
    [router],
  );

  const handleHighlight = useCallback((event: Event) => {
    const target = (event as CustomEvent<{ target: string }>).detail?.target;
    if (!target) return;

    // Try to find element by data-ai-target, id, or CSS selector
    const el =
      document.querySelector(`[data-ai-target="${target}"]`) ??
      document.getElementById(target) ??
      document.querySelector(target);

    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-2", "ring-cyan-400", "ring-offset-2", "transition-all");
      setTimeout(() => {
        el.classList.remove("ring-2", "ring-cyan-400", "ring-offset-2", "transition-all");
      }, 2500);
    }
  }, []);

  useEffect(() => {
    window.addEventListener("ai:open-dialog", handleOpenDialog);
    window.addEventListener("ai:highlight", handleHighlight);
    return () => {
      window.removeEventListener("ai:open-dialog", handleOpenDialog);
      window.removeEventListener("ai:highlight", handleHighlight);
    };
  }, [handleOpenDialog, handleHighlight]);

  function handleDialogAction() {
    if (dialogInfo?.target) {
      router.push(dialogInfo.target);
    }
    setDialogOpen(false);
  }

  return (
    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{dialogInfo?.title ?? "AI Suggestion"}</DialogTitle>
          <DialogDescription>{dialogInfo?.description ?? ""}</DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2 pt-4">
          <button
            type="button"
            onClick={() => setDialogOpen(false)}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Dismiss
          </button>
          <button
            type="button"
            onClick={handleDialogAction}
            className="rounded-md bg-cyan-600 px-3 py-1.5 text-sm text-white hover:bg-cyan-700"
          >
            Go to {dialogInfo?.title ?? "page"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
