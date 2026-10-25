"""HTTP API. Extraction is performed only by the separate worker process."""
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import db
from config import Settings
from processing import validate_pdf
from schemas import Comment, CommentInput, Document, DocumentDetail, DocumentEdit

logger = logging.getLogger('mercura.api')


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        db.initialize(settings)
        yield

    app = FastAPI(title='Mercura Document Extractor', lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
        allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Content-Type'],
    )

    @app.middleware('http')
    async def request_limits(request, call_next):
        length = request.headers.get('content-length')
        if request.method == 'POST' and length:
            try:
                if int(length) > settings.max_upload_bytes + 1024 * 1024:
                    return JSONResponse(status_code=413, content={'detail': 'Upload exceeds the 100 MB limit.'})
            except ValueError:
                return JSONResponse(status_code=400, content={'detail': 'Invalid Content-Length.'})
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, exc):
        logger.error('database_unavailable category=%s', type(exc).__name__)
        return JSONResponse(status_code=503, content={'detail': 'Storage is temporarily unavailable. Please retry.'})

    def get_detail(document_id):
        with db.connect(settings) as conn:
            result = db.detail(conn, document_id)
        if result is None:
            raise HTTPException(404, 'Document not found.')
        return result

    @app.get('/health')
    def health_check():
        with db.connect(settings) as conn:
            conn.execute('SELECT 1').fetchone()
        return {'status': 'ok'}

    @app.get('/api/documents', response_model=list[Document])
    def list_documents():
        with db.connect(settings) as conn:
            ids = [row['id'] for row in conn.execute('SELECT id FROM documents ORDER BY created_at DESC,id')]
            return [db.document(conn, document_id) for document_id in ids]

    @app.delete('/api/documents/{document_id}', status_code=204)
    def delete_document(document_id: str):
        key = db.delete_document(settings, document_id)
        if key is None:
            raise HTTPException(404, 'Document not found.')
        try:
            (settings.uploads / key).unlink(missing_ok=True)
        except OSError:
            logger.warning('deleted_document_file_cleanup_failed')
        return Response(status_code=204)

    @app.post('/api/documents', status_code=202, response_model=DocumentDetail)
    def upload_document(file: UploadFile = File(...)):
        document_id = str(uuid4())
        storage_key = document_id + '.pdf'
        target = settings.uploads / storage_key
        temporary = settings.uploads / (document_id + '.part')
        filename = Path((file.filename or 'document.pdf').replace('\\', '/')).name[:240] or 'document.pdf'
        committed = False
        try:
            size = 0
            with temporary.open('xb') as stream:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, 'PDF exceeds the 100 MB upload limit.')
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                pages = validate_pdf(temporary, settings)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            temporary.replace(target)
            now = db.timestamp()
            with db.connect(settings) as conn:
                conn.execute('BEGIN IMMEDIATE')
                queued = conn.execute("SELECT count(*) FROM extraction_jobs WHERE status IN ('queued','processing')").fetchone()[0]
                if queued >= 200:
                    raise HTTPException(429, 'The processing queue is full. Try again after some documents complete.')
                conn.execute('INSERT INTO documents(id,filename,storage_key,size_bytes,page_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                             (document_id, filename, storage_key, size, pages, now, now))
                conn.execute("INSERT INTO extraction_jobs(id,document_id,status,phase,created_at,updated_at) VALUES(?,?,'queued','queued',?,?)",
                             (str(uuid4()), document_id, now, now))
            committed = True
            logger.info('document_queued document=%s bytes=%s pages=%s', document_id, size, pages)
            return get_detail(document_id)
        finally:
            temporary.unlink(missing_ok=True)
            if not committed:
                target.unlink(missing_ok=True)

    @app.get('/api/documents/{document_id}', response_model=DocumentDetail)
    def get_document(document_id: str):
        return get_detail(document_id)

    @app.patch('/api/documents/{document_id}', response_model=DocumentDetail)
    def edit_document(document_id: str, change: DocumentEdit):
        with db.connect(settings) as conn:
            conn.execute('BEGIN IMMEDIATE')
            current = db.document(conn, document_id)
            if current is None:
                raise HTTPException(404, 'Document not found.')
            if current['job']['status'] != 'completed':
                raise HTTPException(409, 'Wait for extraction to complete before editing.')
            if current['revision'] != change.revision:
                raise HTTPException(409, 'This document changed since you opened it. Reload the latest values before saving.')
            project_id = change.project_id if 'project_id' in change.model_fields_set else current['project_id']
            project_name = change.project_name if 'project_name' in change.model_fields_set else current['project_name']
            conn.execute('UPDATE documents SET project_id=?,project_name=?,revision=revision+1,updated_at=? WHERE id=?',
                         (project_id, project_name, db.timestamp(), document_id))
        return get_detail(document_id)

    @app.post('/api/documents/{document_id}/comments', status_code=201, response_model=Comment)
    def add_comment(document_id: str, comment: CommentInput):
        result = {'id': str(uuid4()), 'text': comment.text, 'created_at': db.timestamp()}
        with db.connect(settings) as conn:
            if not conn.execute('SELECT 1 FROM documents WHERE id=?', (document_id,)).fetchone():
                raise HTTPException(404, 'Document not found.')
            conn.execute('INSERT INTO comments(id,document_id,text,created_at) VALUES(?,?,?,?)',
                         (result['id'], document_id, result['text'], result['created_at']))
        return result

    @app.get('/api/documents/{document_id}/file')
    def download_document(document_id: str):
        with db.connect(settings) as conn:
            row = conn.execute('SELECT storage_key,filename FROM documents WHERE id=?', (document_id,)).fetchone()
        if row is None or not (settings.uploads / row['storage_key']).is_file():
            raise HTTPException(404, 'Original PDF not found.')
        return FileResponse(settings.uploads / row['storage_key'], media_type='application/pdf',
                            filename=row['filename'], content_disposition_type='inline')

    @app.post('/api/documents/{document_id}/retry', status_code=202, response_model=DocumentDetail)
    def retry_document(document_id: str):
        with db.connect(settings) as conn:
            conn.execute('BEGIN IMMEDIATE')
            job = conn.execute('SELECT * FROM extraction_jobs WHERE document_id=?', (document_id,)).fetchone()
            if job is None:
                raise HTTPException(404, 'Document not found.')
            if job['status'] != 'failed':
                raise HTTPException(409, 'Only failed extractions can be retried.')
            conn.execute("""UPDATE extraction_jobs SET status='queued',phase='queued',attempts=0,
                completed_chunks=0,total_chunks=0,error=NULL,claim_token=NULL,lease_until=NULL,
                available_at=0,created_at=?,updated_at=? WHERE document_id=?""",
                (db.timestamp(), db.timestamp(), document_id))
        return get_detail(document_id)

    return app


app = create_app()
