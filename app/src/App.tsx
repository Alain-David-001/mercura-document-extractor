import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { request } from "./api";
import type { DocumentDetail, DocumentRecord } from "./api";
import { formatSize, messageOf } from "./utils";
import Icon from "./components/Icon";
import Status from "./components/Status";
import DocumentPanel from "./components/DocumentPanel";
import type { MetadataDraft } from "./components/MetadataEditor";
import "./App.css";

function App() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [uploading, setUploading] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentRecord | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const generation = useRef(0);
  const [filter, setFilter] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const selection = useRef(selectedId);
  const activeUpload = useRef(false);
  const drafts = useRef(new Map<string, MetadataDraft>());
  const commentDrafts = useRef(new Map<string, string>());
  selection.current = selectedId;

  const refresh = useCallback(async () => {
    const version = generation.current;
    const list = await request<DocumentRecord[]>("/documents");
    if (version !== generation.current) return;
    setDocuments(list);
    const id = list.some((doc) => doc.id === selection.current)
      ? selection.current
      : list[0]?.id || null;
    if (id !== selection.current) {
      selection.current = id;
      setSelectedId(id);
      setDetail(null);
    }
    if (id) {
      const current = await request<DocumentDetail>(`/documents/${id}`).catch(
        (error) => {
          if (version !== generation.current) return null;
          throw error;
        },
      );
      if (!current) return;
      if (selection.current === id && version === generation.current)
        setDetail((previous) =>
          previous?.id === id &&
          (previous.revision > current.revision ||
            previous.job.updated_at > current.job.updated_at ||
            previous.comments.length > current.comments.length)
            ? previous
            : current,
        );
    }
    setError("");
    setLoading(false);
  }, []);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        await refresh();
      } catch (error) {
        if (!stopped) {
          setError(messageOf(error));
          setLoading(false);
        }
      }
      if (!stopped) timer = setTimeout(poll, 2500);
    }
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    request<DocumentDetail>(`/documents/${selectedId}`)
      .then((doc) => {
        if (!cancelled) setDetail(doc);
      })
      .catch((error) => {
        if (!cancelled) setError(messageOf(error));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  function updated(doc: DocumentDetail) {
    if (selection.current !== doc.id) return;
    setDetail(doc);
    setDocuments((list) =>
      list.map((item) => (item.id === doc.id ? doc : item)),
    );
  }

  async function removeDocument() {
    if (!deleteTarget || activeUpload.current) return;
    setDeleting(true);
    setDeleteError("");
    generation.current += 1;
    const target = deleteTarget;
    try {
      await request(`/documents/${target.id}`, { method: "DELETE" });
      generation.current += 1;
      drafts.current.delete(target.id);
      commentDrafts.current.delete(target.id);
      if (selection.current === target.id) {
        selection.current = null;
        setSelectedId(null);
        setDetail(null);
      }
      setDocuments((list) => list.filter((doc) => doc.id !== target.id));
      setDeleteTarget(null);
      await refresh().catch((error) => setError(messageOf(error)));
    } catch (error) {
      setDeleteError(messageOf(error));
    } finally {
      setDeleting(false);
    }
  }

  async function upload(files: FileList | File[]) {
    if (activeUpload.current || deleting) return;
    const queue = Array.from(files);
    if (!queue.length) return;
    activeUpload.current = true;
    setUploadErrors([]);
    setUploading(queue.length);
    let firstUploaded: string | null = null;
    async function send() {
      while (queue.length) {
        const file = queue.shift()!;
        try {
          if (!file.name.toLowerCase().endsWith(".pdf"))
            throw new Error("Choose a PDF file.");
          if (file.size > 100 * 1024 * 1024)
            throw new Error("PDF exceeds the 100 MB upload limit.");
          const body = new FormData();
          body.append("file", file);
          const doc = await request<DocumentDetail>("/documents", {
            method: "POST",
            body,
          });
          if (!firstUploaded) {
            firstUploaded = doc.id;
            if (!selection.current) {
              selection.current = doc.id;
              setSelectedId(doc.id);
              setDetail(doc);
            }
          }
          setDocuments((list) => [
            doc,
            ...list.filter((item) => item.id !== doc.id),
          ]);
        } catch (error) {
          setUploadErrors((errors) => [
            ...errors,
            `${file.name}: ${messageOf(error)}`,
          ]);
        } finally {
          setUploading((count) => count - 1);
        }
      }
    }
    try {
      await Promise.all([send(), send()]);
      await refresh();
    } catch (error) {
      setError(messageOf(error));
    } finally {
      activeUpload.current = false;
      setUploading(0);
      if (input.current) input.current.value = "";
    }
  }
  function choose(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) void upload(event.target.files);
  }
  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (!uploading) void upload(event.dataTransfer.files);
  }
  const visible = documents.filter((doc) =>
    `${doc.filename} ${doc.project_id || ""} ${doc.project_name || ""}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );

  return (
    <div className="app-shell">
      <main className="main-content">
        <header className="page-header">
          <a className="brand" href="/" aria-label="Mercura home">
            mercura.
          </a>
          <h1>
            Documents <span className="count-badge">{documents.length}</span>
          </h1>
        </header>
        {error && (
          <div className="notice error" role="alert">
            <Icon name="alert" />
            <span>
              {error} Your edits remain on screen; the connection will retry
              automatically.
            </span>
          </div>
        )}
        <section
          className={`upload-zone ${dragging ? "dragging" : ""} ${uploading ? "uploading" : ""}`}
          aria-label="Upload PDFs"
          onDragOver={(event) => {
            event.preventDefault();
            if (!uploading) setDragging(true);
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node))
              setDragging(false);
          }}
          onDrop={drop}
        >
          <div className="upload-copy">
            <p>{uploading ? `Uploading ${uploading}…` : "Drop PDFs here"}</p>
            <span>100 MB · 5,000 pages per file</span>
          </div>
          <button
            className="button primary"
            disabled={uploading > 0 || deleting}
            onClick={() => input.current?.click()}
          >
            <Icon name="upload" size={17} />
            {uploading ? "Uploading…" : "Upload documents"}
          </button>
          <input
            ref={input}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            onChange={choose}
            className="sr-only"
            aria-label="Choose PDF documents"
          />
        </section>
        {uploadErrors.length > 0 && (
          <div className="notice error" role="alert">
            <div>
              <strong>Some files could not be uploaded</strong>
              {uploadErrors.map((item, index) => (
                <p key={index}>{item}</p>
              ))}
            </div>
            <button
              className="icon-button"
              aria-label="Dismiss upload errors"
              onClick={() => setUploadErrors([])}
            >
              <Icon name="close" />
            </button>
          </div>
        )}
        <div className="workspace-grid">
          <section className="document-list" aria-label="Documents">
            <div className="search-wrap">
              <input
                type="search"
                aria-label="Search documents"
                placeholder="Search documents or projects…"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              />
            </div>
            <div className="list-items">
              {loading ? (
                <div className="list-placeholder">Loading…</div>
              ) : visible.length ? (
                visible.map((doc) => (
                  <button
                    key={doc.id}
                    className={`document-item ${selectedId === doc.id ? "selected" : ""}`}
                    onClick={() => {
                      selection.current = doc.id;
                      setSelectedId(doc.id);
                    }}
                    aria-pressed={selectedId === doc.id}
                  >
                    <div className="document-top">
                      <span className="pdf-icon">
                        <Icon name="file" size={21} />
                      </span>
                      <div>
                        <strong>{doc.filename}</strong>
                        <span>
                          {doc.page_count}{" "}
                          {doc.page_count === 1 ? "page" : "pages"} <i>·</i>{" "}
                          {formatSize(doc.size_bytes)}
                        </span>
                      </div>
                    </div>
                    <div className="document-bottom">
                      <Status doc={doc} />
                      <span>
                        {new Date(doc.created_at).toLocaleDateString(
                          undefined,
                          { month: "short", day: "numeric" },
                        )}
                      </span>
                    </div>
                  </button>
                ))
              ) : (
                <div className="list-placeholder">
                  <Icon name="file" size={30} />
                  <strong>{filter ? "No matches" : "No documents"}</strong>
                  <p>
                    {filter
                      ? "Try a different filename or project."
                      : "Upload a PDF to get started."}
                  </p>
                </div>
              )}
            </div>
          </section>
          {selectedId && detail?.id === selectedId ? (
            <DocumentPanel
              key={detail.id}
              doc={detail}
              onUpdated={updated}
              onDelete={() => {
                setDeleteError("");
                setDeleteTarget(detail);
              }}
              drafts={drafts.current}
              commentDrafts={commentDrafts.current}
            />
          ) : (
            <section className="empty-detail">
              <p>
                {selectedId
                  ? "Opening document…"
                  : "Select a document to review."}
              </p>
            </section>
          )}
        </div>
        {deleteTarget && (
          <dialog
            ref={(element) => {
              if (element && !element.open) element.showModal();
            }}
            onCancel={(event) => {
              event.preventDefault();
              if (!deleting) setDeleteTarget(null);
            }}
            aria-modal="true"
            aria-labelledby="delete-title"
            aria-describedby="delete-description"
            className="confirm-dialog"
          >
            <h2 id="delete-title">Delete document?</h2>
            <p id="delete-description">
              “{deleteTarget.filename}” and its extracted data, edits, and
              comments will be permanently deleted.
            </p>
            {deleteError && (
              <p className="inline-error" role="alert">
                {deleteError}
              </p>
            )}
            <div className="dialog-actions">
              <button
                autoFocus
                className="button secondary"
                disabled={deleting}
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                className="button danger"
                disabled={deleting || uploading > 0}
                onClick={() => void removeDocument()}
              >
                {deleting ? "Deleting…" : "Delete document"}
              </button>
            </div>
          </dialog>
        )}
      </main>
    </div>
  );
}
export default App;
