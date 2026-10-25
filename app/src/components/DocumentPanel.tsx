import { useState } from "react";
import type { FormEvent } from "react";
import { jsonBody, request } from "../api";
import type { DocumentDetail } from "../api";
import { formatDate, formatSize, messageOf } from "../utils";
import Icon from "./Icon";
import Status from "./Status";
import MetadataEditor from "./MetadataEditor";
import type { MetadataDraft } from "./MetadataEditor";

export default function DocumentPanel({
  doc,
  onUpdated,
  drafts,
  commentDrafts,
}: {
  doc: DocumentDetail;
  onUpdated: (doc: DocumentDetail) => void;
  drafts: Map<string, MetadataDraft>;
  commentDrafts: Map<string, string>;
}) {
  const [comment, setComment] = useState(commentDrafts.get(doc.id) || "");
  const [commenting, setCommenting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState("");
  async function addComment(event: FormEvent) {
    event.preventDefault();
    setCommenting(true);
    setError("");
    try {
      await request(`/documents/${doc.id}/comments`, {
        method: "POST",
        ...jsonBody({ text: comment }),
      });
      setComment("");
      commentDrafts.delete(doc.id);
      onUpdated(await request<DocumentDetail>(`/documents/${doc.id}`));
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setCommenting(false);
    }
  }
  async function retry() {
    setRetrying(true);
    setError("");
    try {
      onUpdated(
        await request<DocumentDetail>(`/documents/${doc.id}/retry`, {
          method: "POST",
        }),
      );
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setRetrying(false);
    }
  }
  const job = doc.job;
  return (
    <article className="detail-panel">
      <header className="detail-header">
        <div className="eyebrow">DOCUMENT REVIEW</div>
        <div className="detail-title">
          <h2>{doc.filename}</h2>
          <a
            className="button secondary small"
            href={`/api/documents/${doc.id}/file`}
            target="_blank"
            rel="noreferrer"
          >
            Open PDF <Icon name="arrow" size={16} />
          </a>
        </div>
        <div className="file-meta">
          <span>
            {doc.page_count} {doc.page_count === 1 ? "page" : "pages"}
          </span>
          <span>{formatSize(doc.size_bytes)}</span>
          <span>Added {formatDate(doc.created_at)}</span>
        </div>
      </header>
      <div className="detail-body">
        <div className="section-heading">
          <h3>Project details</h3>
          <Status doc={doc} />
        </div>
        {job.status === "completed" ? (
          <>
            {doc.warning && (
              <div role="status" className="notice warning">
                <Icon name="alert" />
                <span>{doc.warning}</span>
              </div>
            )}
            <MetadataEditor doc={doc} onUpdated={onUpdated} drafts={drafts} />
          </>
        ) : (
          <div
            className={`processing-card ${job.status === "failed" ? "failed-card" : ""}`}
          >
            <span
              className={
                job.status === "processing"
                  ? "processing-icon spinning"
                  : "processing-icon"
              }
            >
              <Icon
                name={job.status === "failed" ? "alert" : "clock"}
                size={25}
              />
            </span>
            <h4>
              {job.status === "failed"
                ? "Extraction needs attention"
                : job.status === "queued"
                  ? job.phase === "retry_wait"
                    ? "Waiting to retry"
                    : "Your document is in the queue"
                  : job.phase === "preparing"
                    ? "Preparing your PDF"
                    : "Finding the project details"}
            </h4>
            <p>
              {job.status === "failed"
                ? job.error
                : job.status === "queued"
                  ? "The worker will pick it up automatically. You can keep uploading and reviewing other documents."
                  : "Gemini is reading your document. Results will appear here automatically."}
            </p>
            {job.total_chunks > 0 && (
              <div className="chunk-progress">
                <progress
                  max={job.total_chunks}
                  value={job.completed_chunks}
                  aria-label="Completed PDF chunks"
                />
                <span>
                  {job.completed_chunks} of {job.total_chunks} chunks processed
                </span>
              </div>
            )}
            {job.status === "queued" && job.error && (
              <p className="muted">{job.error}</p>
            )}
            {job.status === "failed" && (
              <button
                className="button primary"
                disabled={retrying}
                onClick={retry}
              >
                {retrying ? "Queuing…" : "Retry extraction"}
              </button>
            )}
          </div>
        )}
        <section className="comments-section">
          <div className="section-heading">
            <h3>
              <Icon name="message" size={18} /> Comments{" "}
              <span className="count-badge">{doc.comments.length}</span>
            </h3>
          </div>
          {doc.comments.length === 0 ? (
            <p className="empty-comments">
              Keep review notes and context together with the document.
            </p>
          ) : (
            <ol className="comment-list">
              {doc.comments.map((item) => (
                <li key={item.id}>
                  <div className="comment-top">
                    <span className="avatar">Y</span>
                    <strong>You</strong>
                    <time dateTime={item.created_at}>
                      {formatDate(item.created_at)}
                    </time>
                  </div>
                  <p>{item.text}</p>
                </li>
              ))}
            </ol>
          )}
          <form onSubmit={addComment}>
            <label className="sr-only" htmlFor="new-comment">
              Add a comment
            </label>
            <textarea
              id="new-comment"
              placeholder="Add a note about this document…"
              value={comment}
              disabled={commenting}
              maxLength={4000}
              onChange={(event) => {
                setComment(event.target.value);
                commentDrafts.set(doc.id, event.target.value);
              }}
            />
            <div className="comment-footer">
              <span className="muted">
                {comment.length > 3500
                  ? `${comment.length}/4000`
                  : "Notes are saved with this document."}
              </span>
              <button
                className="button secondary"
                disabled={!comment.trim() || commenting}
              >
                {commenting ? "Adding…" : "Add comment"}
              </button>
            </div>
          </form>
        </section>
        {error && (
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </article>
  );
}
