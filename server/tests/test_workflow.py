import asyncio
import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

import db
from config import Settings
from main import create_app
from processing import ExtractionError, merge_metadata, prepare_chunks
from schemas import Metadata
from worker import process_job, run


def pdf_bytes(pages=1, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if encrypted:
        writer.encrypt('password')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def settings(tmp_path):
    result = Settings(data_dir=tmp_path, chunk_pages=2, poll_seconds=0.01)
    db.initialize(result)
    return result


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def upload(client, name='specification.pdf', pages=1):
    response = client.post('/api/documents', files={'file': (name, pdf_bytes(pages), 'application/pdf')})
    assert response.status_code == 202, response.text
    return response.json()


class FakeExtractor:
    async def extract(self, path, first_page, last_page):
        assert len(PdfReader(path).pages) == last_page - first_page + 1
        return Metadata(project_id='PROJECT-42', project_name='Construction project')


def complete(settings):
    job = db.claim(settings)
    assert job
    asyncio.run(process_job(settings, job, FakeExtractor()))
    return job


def test_upload_extract_edit_comment_download_and_restart(client, settings):
    original_pdf = pdf_bytes(3)
    response = client.post('/api/documents', files={'file': ('../../unsafe.pdf', original_pdf, 'application/pdf')})
    assert response.status_code == 202
    doc = response.json()
    assert doc['filename'] == 'unsafe.pdf'
    assert doc['page_count'] == 3
    assert doc['job']['status'] == 'queued'
    assert 'storage_key' not in doc
    assert len(list(settings.uploads.glob('*.pdf'))) == 1
    assert not list(settings.uploads.glob('*.part'))
    assert client.patch(f"/api/documents/{doc['id']}", json={'revision': 0, 'project_name': 'too early'}).status_code == 409
    complete(settings)
    ready = client.get(f"/api/documents/{doc['id']}").json()
    assert ready['job']['status'] == 'completed'
    assert ready['job']['completed_chunks'] == ready['job']['total_chunks'] == 2
    assert ready['project_id'] == 'PROJECT-42'
    edited = client.patch(f"/api/documents/{doc['id']}", json={'revision': 0, 'project_name': '  Reviewed project  '})
    assert edited.status_code == 200
    assert edited.json()['project_name'] == 'Reviewed project'
    assert edited.json()['project_id'] == 'PROJECT-42'
    assert edited.json()['ai_project_name'] == 'Construction project'
    assert edited.json()['revision'] == 1
    stale = client.patch(f"/api/documents/{doc['id']}", json={'revision': 0, 'project_name': 'stale'})
    assert stale.status_code == 409
    comment = client.post(f"/api/documents/{doc['id']}/comments", json={'text': '  Checked against original  '})
    assert comment.status_code == 201
    downloaded = client.get(f"/api/documents/{doc['id']}/file")
    assert downloaded.content == original_pdf
    assert downloaded.headers['content-type'] == 'application/pdf'
    assert client.post(f"/api/documents/{doc['id']}/retry").status_code == 409
    with TestClient(create_app(settings)) as restarted:
        persisted = restarted.get(f"/api/documents/{doc['id']}").json()
        assert persisted['project_name'] == 'Reviewed project'
        assert persisted['comments'][0]['text'] == 'Checked against original'
        assert restarted.get('/api/documents').json()[0]['id'] == doc['id']


@pytest.mark.parametrize('content', [b'', b'not a PDF', b'%PDF-1.7\ntruncated'])
def test_invalid_pdfs_leave_no_records_or_files(client, settings, content):
    response = client.post('/api/documents', files={'file': ('invalid.pdf', content, 'application/pdf')})
    assert response.status_code == 422
    assert client.get('/api/documents').json() == []
    assert list(settings.uploads.iterdir()) == []


def test_encrypted_pdf_rejected(client):
    response = client.post('/api/documents', files={'file': ('locked.pdf', pdf_bytes(encrypted=True), 'application/pdf')})
    assert response.status_code == 422
    assert 'Password-protected' in response.json()['detail']


def test_page_limit_and_size_limit(settings):
    restricted = replace(settings, max_pages=1, max_upload_bytes=600)
    with TestClient(create_app(restricted)) as client:
        assert client.post('/api/documents', files={'file': ('large.pdf', b'%PDF-' + b'x' * 1000)}).status_code == 413
        assert client.post('/api/documents', files={'file': ('pages.pdf', pdf_bytes(2))}).status_code == 422


def test_missing_document_and_invalid_comment(client):
    assert client.get('/api/documents/missing').status_code == 404
    assert client.get('/api/documents/missing/file').status_code == 404
    assert client.post('/api/documents/missing/retry').status_code == 404
    doc = upload(client)
    assert client.post(f"/api/documents/{doc['id']}/comments", json={'text': '  '}).status_code == 422
    assert client.post('/api/documents/missing/comments', json={'text': 'Note'}).status_code == 404
    assert client.patch(f"/api/documents/{doc['id']}", json={'revision': -1}).status_code == 422


def test_atomic_claims(client, settings):
    ids = {upload(client)['id'] for _ in range(2)}
    barrier = threading.Barrier(2)
    def take():
        barrier.wait(timeout=3)
        return db.claim(settings)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: take(), range(2)))
    assert {job['document_id'] for job in jobs} == ids
    assert jobs[0]['claim_token'] != jobs[1]['claim_token']
    assert db.claim(settings) is None


def test_expired_claim_recovers_and_stale_worker_cannot_write(client, settings):
    doc = upload(client)
    old = db.claim(settings)
    with db.connect(settings) as conn:
        conn.execute('UPDATE extraction_jobs SET lease_until=? WHERE id=?', (time.time() - 1, old['id']))
    new = db.claim(settings)
    assert new['document_id'] == doc['id']
    assert new['attempts'] == 2
    with pytest.raises(db.LostClaim):
        db.finish(settings, old, Metadata(project_id='stale'))
    with pytest.raises(db.LostClaim):
        db.progress(settings, old, 'extracting')
    db.finish(settings, new, Metadata(project_id='new'))
    assert client.get(f"/api/documents/{doc['id']}").json()['project_id'] == 'new'


def test_interruption_attempts_are_bounded(client, settings):
    doc = upload(client)
    for attempt in range(settings.max_attempts):
        job = db.claim(settings)
        assert job['attempts'] == attempt + 1
        with db.connect(settings) as conn:
            conn.execute('UPDATE extraction_jobs SET lease_until=0 WHERE id=?', (job['id'],))
    assert db.claim(settings) is None
    assert client.get(f"/api/documents/{doc['id']}").json()['job']['status'] == 'failed'


def test_transient_retry_and_manual_retry(client, settings):
    doc = upload(client)
    job = db.claim(settings)
    db.fail(settings, job, 'Provider busy', transient=True)
    queued = client.get(f"/api/documents/{doc['id']}").json()
    assert queued['job']['phase'] == 'retry_wait'
    assert db.claim(settings) is None
    with db.connect(settings) as conn:
        conn.execute('UPDATE extraction_jobs SET available_at=0')
    job = db.claim(settings)
    db.fail(settings, job, 'Invalid credentials', transient=False)
    assert client.get(f"/api/documents/{doc['id']}").json()['job']['status'] == 'failed'
    assert client.post(f"/api/documents/{doc['id']}/retry").status_code == 202
    assert client.post(f"/api/documents/{doc['id']}/retry").status_code == 409
    assert db.claim(settings)['attempts'] == 1


def test_worker_provider_failure_is_persisted(client, settings):
    doc = upload(client)
    class BrokenExtractor:
        async def extract(self, *args):
            raise ExtractionError('Test provider failure')
    asyncio.run(process_job(settings, db.claim(settings), BrokenExtractor()))
    failed = client.get(f"/api/documents/{doc['id']}").json()
    assert failed['job']['status'] == 'failed'
    assert failed['job']['error'] == 'Test provider failure'
    assert not list(settings.data_dir.glob('job-*'))


def test_chunks_respect_page_and_byte_limits(tmp_path, settings):
    path = tmp_path / 'source.pdf'
    path.write_bytes(pdf_bytes(5))
    directory = tmp_path / 'chunks'
    directory.mkdir()
    chunks = prepare_chunks(path, directory, replace(settings, chunk_pages=5, chunk_bytes=650))
    assert len(chunks) > 1
    assert sum(len(PdfReader(chunk).pages) for chunk, _, _ in chunks) == 5
    assert all(chunk.stat().st_size <= 650 for chunk, _, _ in chunks)
    assert chunks[0][1] == 1 and chunks[-1][2] == 5
    too_small = tmp_path / 'small'
    too_small.mkdir()
    with pytest.raises(ExtractionError):
        prepare_chunks(path, too_small, replace(settings, chunk_bytes=10))


def test_conflicting_or_missing_values_are_visible():
    result, warning = merge_metadata([Metadata(project_id='A', project_name='First'), Metadata(project_id='B', project_name='first')])
    assert result.project_id == 'A'
    assert 'Conflicting project id' in warning
    assert 'Conflicting project name' not in warning
    result, warning = merge_metadata([Metadata()])
    assert result.project_id is None
    assert 'No project id' in warning and 'No project name' in warning


def test_two_jobs_really_process_concurrently(client, settings, monkeypatch):
    for _ in range(2):
        upload(client)
    async def scenario():
        loop = asyncio.get_running_loop()
        both_started = asyncio.Event()
        all_finished = asyncio.Event()
        finished = 0
        original_finish = db.finish
        def mark_finished():
            nonlocal finished
            finished += 1
            if finished == 2:
                all_finished.set()
        def tracked_finish(*args):
            original_finish(*args)
            loop.call_soon_threadsafe(mark_finished)
        monkeypatch.setattr(db, 'finish', tracked_finish)
        class ConcurrentExtractor:
            active = 0
            async def extract(self, *args):
                self.active += 1
                if self.active == 2:
                    both_started.set()
                await asyncio.wait_for(both_started.wait(), timeout=3)
                return Metadata(project_id='parallel')
        stop = asyncio.Event()
        task = asyncio.create_task(run(replace(settings, concurrency=2), ConcurrentExtractor(), stop))
        try:
            await asyncio.wait_for(all_finished.wait(), timeout=5)
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=3)
    asyncio.run(scenario())
    assert all(item['job']['status'] == 'completed' for item in client.get('/api/documents').json())


def test_gemini_contract_validates_output_and_cleans_up(settings, tmp_path):
    from types import SimpleNamespace
    from google.genai import types
    from processing import GeminiExtractor

    deleted = []
    class Files:
        async def upload(self, **kwargs):
            return SimpleNamespace(name='test-file', state=None)
        async def delete(self, **kwargs):
            deleted.append(kwargs['name'])
    class Models:
        async def generate_content(self, **kwargs):
            schema = kwargs['config'].response_schema
            assert isinstance(schema, types.Schema)
            assert schema.required == ['project_id', 'project_name']
            return SimpleNamespace(text='{"project_id":"TEST-1","project_name":"Test"}')
    extractor = object.__new__(GeminiExtractor)
    extractor.settings = settings
    extractor.client = SimpleNamespace(aio=SimpleNamespace(files=Files(), models=Models()))
    result = asyncio.run(extractor.extract(tmp_path / 'test.pdf', 1, 1))
    assert result.project_id == 'TEST-1'
    assert deleted == ['test-file']

    class InvalidModels:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text='{"project_id":"' + 'x' * 201 + '"}')
    extractor.client.aio.models = InvalidModels()
    with pytest.raises(ExtractionError, match='invalid result'):
        asyncio.run(extractor.extract(tmp_path / 'test.pdf', 1, 1))
    assert deleted == ['test-file', 'test-file']


def test_thousand_page_document_uses_bounded_chunks(client, settings):
    large = replace(settings, chunk_pages=40)
    payload = pdf_bytes(1001)
    response = client.post('/api/documents', files={'file': ('large-specification.pdf', payload, 'application/pdf')})
    assert response.status_code == 202
    job = db.claim(large)
    seen = []
    class CountingExtractor(FakeExtractor):
        async def extract(self, path, first_page, last_page):
            assert last_page - first_page + 1 <= large.chunk_pages
            assert path.stat().st_size <= large.chunk_bytes
            seen.append((first_page, last_page))
            return await super().extract(path, first_page, last_page)
    asyncio.run(process_job(large, job, CountingExtractor()))
    doc = client.get(f"/api/documents/{response.json()['id']}").json()
    assert doc['job']['status'] == 'completed'
    assert doc['job']['total_chunks'] == 26
    assert len(seen) == 26 and seen[0][0] == 1 and seen[-1][1] == 1001
