import type { DocumentRecord } from "../api";

const statusLabels = {
  queued: "Queued",
  processing: "Processing",
  completed: "Ready to review",
  failed: "Needs attention",
};
export default function Status({ doc }: { doc: DocumentRecord }) {
  return (
    <span className={`status ${doc.job.status}`}>
      <span className="status-dot" />
      {statusLabels[doc.job.status]}
    </span>
  );
}
