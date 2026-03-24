"use client";

import { useEffect } from "react";

import { reportClientRuntimeEvent } from "@/lib/api";

export function RuntimeEventListeners() {
  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      if (!event.message) return;
      void reportClientRuntimeEvent({
        event_type: "ui_error",
        level: "error",
        message: event.message,
        details: {
          filename: event.filename || "unknown",
          lineno: event.lineno ?? 0,
          colno: event.colno ?? 0,
        },
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const reason =
        typeof event.reason === "string"
          ? event.reason
          : event.reason instanceof Error
            ? event.reason.message
            : "Unhandled promise rejection";
      void reportClientRuntimeEvent({
        event_type: "unhandled_rejection",
        level: "error",
        message: reason,
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);
    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  return null;
}
