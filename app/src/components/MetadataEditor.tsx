import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { jsonBody, request } from "../api";
import type { DocumentDetail } from "../api";
import { messageOf } from "../utils";

export interface MetadataDraft {
  projectId: string;
  projectName: string;
  revision: number;
}

export default function MetadataEditor({
  doc,
  onUpdated,
  drafts,
}: {
  doc: DocumentDetail;
  onUpdated: (doc: DocumentDetail) => void;
  drafts: Map<string, MetadataDraft>;
}) {
  const draft = drafts.get(doc.id);
  const [projectId, setProjectId] = useState(
    draft?.projectId ?? doc.project_id ?? "",
  );
  const [projectName, setProjectName] = useState(
    draft?.projectName ?? doc.project_name ?? "",
  );
  const [revision, setRevision] = useState(draft?.revision ?? doc.revision);
  const [dirty, setDirty] = useState(Boolean(draft));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!dirty) {
      setProjectId(doc.project_id || "");
      setProjectName(doc.project_name || "");
      setRevision(doc.revision);
    }
  }, [doc.project_id, doc.project_name, doc.revision, dirty]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const updated = await request<DocumentDetail>(`/documents/${doc.id}`, {
        method: "PATCH",
        ...jsonBody({
          project_id: projectId,
          project_name: projectName,
          revision,
        }),
      });
      drafts.delete(doc.id);
      onUpdated(updated);
      setRevision(updated.revision);
      setDirty(false);
      setSaved(true);
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setSaving(false);
    }
  }
  return (
    <form onSubmit={save} className="metadata-form">
      <label htmlFor="project-id">Project ID</label>
      <input
        id="project-id"
        value={projectId}
        maxLength={200}
        disabled={saving}
        placeholder="Not found — enter a project ID"
        onChange={(event) => {
          setProjectId(event.target.value);
          drafts.set(doc.id, {
            projectId: event.target.value,
            projectName,
            revision,
          });
          setDirty(true);
          setSaved(false);
        }}
      />
      <label htmlFor="project-name">Project name</label>
      <input
        id="project-name"
        value={projectName}
        maxLength={1000}
        disabled={saving}
        placeholder="Not found — enter a project name"
        onChange={(event) => {
          setProjectName(event.target.value);
          drafts.set(doc.id, {
            projectId,
            projectName: event.target.value,
            revision,
          });
          setDirty(true);
          setSaved(false);
        }}
      />
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      {dirty && revision !== doc.revision && (
        <div className="notice warning">
          A newer revision is available. Your draft is preserved.{" "}
          <button
            type="button"
            className="text-button"
            onClick={() => {
              drafts.delete(doc.id);
              setDirty(false);
              setError("");
            }}
          >
            Load latest values
          </button>
        </div>
      )}
      <div className="form-footer">
        <span className={saved ? "saved-note" : "muted"} role="status">
          {saved
            ? "Changes saved"
            : dirty
              ? "Unsaved changes"
              : "Review the extracted values before using them."}
        </span>
        <button className="button primary" disabled={!dirty || saving}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
      <details className="original-values">
        <summary>Original AI extraction</summary>
        <dl>
          <dt>Project ID</dt>
          <dd>{doc.ai_project_id || "Not found"}</dd>
          <dt>Project name</dt>
          <dd>{doc.ai_project_name || "Not found"}</dd>
        </dl>
      </details>
    </form>
  );
}
