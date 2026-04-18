import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { ReportPreviewClient } from "./report-preview-client";

function ReportPreviewFallback() {
  return (
    <div className="flex min-h-[400px] items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
    </div>
  );
}

export default function ReportPreviewPage() {
  return (
    <Suspense fallback={<ReportPreviewFallback />}>
      <ReportPreviewClient />
    </Suspense>
  );
}
