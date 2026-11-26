import io
import zipfile
from pathlib import Path

import pytest

import app as jobmatrix

SAMPLES = Path(__file__).resolve().parent.parent / 'Resumes_NLP'
JD = ('Software engineer. Build web applications in Python and JavaScript. SQL databases, '
      'REST APIs, Docker, AWS, Git, agile teams, unit testing and code reviews.')


@pytest.fixture
def client():
    jobmatrix.app.config['TESTING'] = True
    return jobmatrix.app.test_client()


def upload(name, data):
    return (io.BytesIO(data), name)


def make_docx(text, extra_size=0):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        body = f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' \
               f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
        zf.writestr('word/document.xml', body + ' ' * extra_size)
    return buf.getvalue()


# --- Pages ------------------------------------------------------------------

@pytest.mark.parametrize('path', ['/', '/learn', '/about', '/match', '/robots.txt', '/favicon.ico',
                                  '/static/site.webmanifest', '/static/icons/favicon.svg'])
def test_pages_load(client, path):
    assert client.get(path).status_code == 200


def test_unknown_page_is_404(client):
    res = client.get('/does-not-exist')
    assert res.status_code == 404
    assert b'Page not found' in res.data


def test_method_not_allowed(client):
    assert client.delete('/match').status_code == 405


def test_security_headers(client):
    h = client.get('/').headers
    assert "script-src 'self'" in h['Content-Security-Policy']
    assert "frame-ancestors 'none'" in h['Content-Security-Policy']
    assert h['X-Content-Type-Options'] == 'nosniff'
    assert h['X-Frame-Options'] == 'DENY'
    assert 'Referrer-Policy' in h


def test_pages_have_no_inline_scripts(client):
    """The CSP forbids inline scripts, so none may exist."""
    for path in ['/', '/learn', '/about', '/match']:
        html = client.get(path).get_data(as_text=True)
        assert '<script>' not in html


# --- Matching ---------------------------------------------------------------

def test_ranks_resumes_best_first(client):
    res = client.post('/match', data={
        'jd-text': JD,
        'resumes-file': [
            upload('strong.txt', b'Python developer: SQL, REST APIs, Docker, AWS, Git, agile, unit testing.'),
            upload('weak.txt', b'Marketing manager focused on SEO, campaigns and social media.'),
        ],
    }, content_type='multipart/form-data')
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert html.index('strong.txt') < html.index('weak.txt')
    assert res.headers['Cache-Control'] == 'no-store'


def test_sample_resumes(client):
    if not SAMPLES.exists():
        pytest.skip('sample resumes not present')
    files = [upload(p.name, p.read_bytes()) for p in SAMPLES.iterdir()
             if p.suffix in {'.txt', '.pdf', '.docx'} and p.name != 'JD.txt']
    res = client.post('/match', data={'jd-text': (SAMPLES / 'JD.txt').read_text(encoding='utf-8'),
                                      'resumes-file': files}, content_type='multipart/form-data')
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert html.count('class="result reveal"') == 5


def test_docx_is_read(client):
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('cv.docx', make_docx('Python SQL Docker AWS'))]},
                      content_type='multipart/form-data')
    assert res.status_code == 200
    assert b'cv.docx' in res.data


def test_missing_job_description(client):
    res = client.post('/match', data={'resumes-file': [upload('a.txt', b'python')]}, content_type='multipart/form-data')
    assert res.status_code == 400
    assert b'Add a job description' in res.data


def test_missing_resumes(client):
    res = client.post('/match', data={'jd-text': JD}, content_type='multipart/form-data')
    assert res.status_code == 400
    assert b'Add at least one resume' in res.data


def test_stop_words_only(client):
    res = client.post('/match', data={'jd-text': 'the and of', 'resumes-file': [upload('a.txt', b'the and of')]},
                      content_type='multipart/form-data')
    assert res.status_code == 400


# --- Hostile input ----------------------------------------------------------

def test_disallowed_extension_is_skipped(client):
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('evil.exe', b'MZ\x90\x00')]},
                      content_type='multipart/form-data')
    assert res.status_code == 400


def test_fake_pdf_is_rejected(client):
    """A renamed file must not reach the PDF parser."""
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('fake.pdf', b'just text')]},
                      content_type='multipart/form-data')
    assert res.status_code == 400


def test_corrupt_pdf_does_not_crash(client):
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('bad.pdf', b'%PDF-1.4\n garbage')]},
                      content_type='multipart/form-data')
    assert res.status_code == 400


def test_docx_zip_bomb_is_rejected(client):
    bomb = make_docx('python', extra_size=jobmatrix.MAX_DOCX_UNCOMPRESSED + 1)
    assert len(bomb) < 1_000_000  # small on the wire, huge when expanded
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('bomb.docx', bomb)]},
                      content_type='multipart/form-data')
    assert res.status_code == 400


def test_html_in_resume_is_escaped(client):
    payload = b'<script>alert(1)</script> python sql docker'
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('<img src=x onerror=alert(1)>.txt', payload)]},
                      content_type='multipart/form-data')
    html = res.get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert 'onerror=alert' not in html or '&lt;' in html


def test_path_traversal_filename_is_sanitised(client):
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('../../etc/passwd.txt', b'python sql docker')]},
                      content_type='multipart/form-data')
    assert res.status_code == 200
    assert b'../' not in res.data


def test_too_many_resumes(client):
    files = [upload(f'r{i}.txt', b'python') for i in range(jobmatrix.MAX_RESUMES + 1)]
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': files}, content_type='multipart/form-data')
    assert res.status_code == 400
    assert b'at most' in res.data


def test_oversized_upload_is_rejected(client):
    big = b'a ' * (9 * 1024 * 1024)  # ~18 MB
    res = client.post('/match', data={'jd-text': JD, 'resumes-file': [upload('big.txt', big)]},
                      content_type='multipart/form-data')
    assert res.status_code == 413
