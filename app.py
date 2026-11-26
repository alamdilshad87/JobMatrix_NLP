"""JobMatrix: rank resumes against a job description with TF-IDF and cosine similarity."""
import io
import logging
import os
import re
import secrets
import zipfile
from datetime import datetime

import docx2txt
from flask import Flask, flash, render_template, request, send_from_directory
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.utils import secure_filename

DEBUG = os.environ.get('FLASK_DEBUG') == '1'

app = Flask(__name__, template_folder='template')
app.config.update(
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,      # 16 MB per request, enforced by Werkzeug
    MAX_FORM_PARTS=200,                       # caps multipart parts (Werkzeug DoS guard)
    TEMPLATES_AUTO_RELOAD=DEBUG,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', '0') == '1',
)
# Only used to sign the flash-message cookie. Set SECRET_KEY in production so it is stable
# across restarts and workers; a random one is generated otherwise.
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('jobmatrix')

# .doc (old binary Word) is deliberately not accepted: docx2txt can only read .docx.
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
TOP_N = 5
JD_KEY_TERMS = 15

# Resource limits, so one request can't tie up the server
MAX_RESUMES = 50
MAX_PDF_PAGES = 30
MAX_TEXT_CHARS = 100_000                      # per document, after extraction
MAX_DOCX_UNCOMPRESSED = 25 * 1024 * 1024      # zip-bomb guard for .docx

TEAM = [
    {
        'name': 'Md Dilshad Alam',
        'role': 'Team Lead & UI Designer',
        'photo': 'Dilshad.jpg',
        'github': 'https://github.com/alamdilshad87',
        'linkedin': 'https://www.linkedin.com/in/alamdilshad87/',
        'bio': 'Led the project and designed the interface, turning the matching pipeline into a clean, '
               'recruiter-friendly flow from upload to ranked results.',
    },
    {
        'name': 'Soubhagya Biswas',
        'role': 'Backend Developer',
        'photo': 'biswas.jpeg',
        'github': 'https://github.com/Soub1101',
        'linkedin': 'https://www.linkedin.com/in/soubhagya-biswas-a956851ba/',
        'bio': 'Built the Flask backend and the core matching algorithm with TF-IDF and cosine similarity, '
               'including text extraction from PDF, DOCX and TXT files.',
    },
    {
        'name': 'Prachi Singhal',
        'role': 'Data Analyst & Tester',
        'photo': 'Prachi.jpg',
        'github': 'https://github.com/prachisinghal31/',
        'linkedin': 'https://www.linkedin.com/in/prachisinghal31',
        'bio': 'Tested the matcher against sample job descriptions and resumes, checked the rankings for '
               'accuracy, and fed results back into the scoring.',
    },
]


@app.context_processor
def inject_globals():
    return {'current_year': datetime.now().year, 'team': TEAM}


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "form-action 'self'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
])


@app.after_request
def set_security_headers(response):
    response.headers.setdefault('Content-Security-Policy', CSP)
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), interest-cohort=()')
    response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    # Results pages contain uploaded resume text: never cache them
    if request.method == 'POST':
        response.headers['Cache-Control'] = 'no-store'
    return response


# ---------------------------------------------------------------------------
# Text extraction (entirely in memory: uploads are never written to disk)
# ---------------------------------------------------------------------------

class UnreadableFile(Exception):
    """The file is the wrong type, malformed, or too large to process safely."""


def file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def allowed_file(filename):
    return file_extension(filename) in ALLOWED_EXTENSIONS


def clean_text(text):
    text = text.replace('\x00', ' ')
    return text[:MAX_TEXT_CHARS].strip()


def extract_pdf(data):
    if not data.startswith(b'%PDF'):
        raise UnreadableFile('not a PDF')
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise UnreadableFile('encrypted PDF')
    parts, length = [], 0
    for page in reader.pages[:MAX_PDF_PAGES]:
        chunk = page.extract_text() or ''
        parts.append(chunk)
        length += len(chunk)
        if length >= MAX_TEXT_CHARS:
            break
    return '\n'.join(parts)


def extract_docx(data):
    if not data.startswith(b'PK'):
        raise UnreadableFile('not a DOCX')
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        if 'word/document.xml' not in names:
            raise UnreadableFile('not a Word document')
        # docx2txt only reads the body, header and footer parts; their declared sizes cap
        # how much Python's zip reader will decompress, so check them before reading.
        wanted = [i for i in zf.infolist()
                  if i.filename == 'word/document.xml' or re.match(r'word/(header|footer)\d*\.xml$', i.filename)]
        if sum(i.file_size for i in wanted) > MAX_DOCX_UNCOMPRESSED:
            raise UnreadableFile('DOCX expands too large')
    return docx2txt.process(io.BytesIO(data))


def extract_txt(data):
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='ignore')


EXTRACTORS = {'pdf': extract_pdf, 'docx': extract_docx, 'txt': extract_txt}


def read_upload(file_storage, fallback_name):
    """Return (display_name, text). Text is '' when the file can't be read."""
    original = file_storage.filename or ''
    ext = file_extension(original)
    name = secure_filename(original) or fallback_name
    if not name.lower().endswith('.' + ext):
        name = f'{fallback_name}.{ext}'
    data = file_storage.read()
    try:
        return name, clean_text(EXTRACTORS[ext](data) or '')
    except UnreadableFile as e:
        log.info('Rejected %s upload: %s', ext, e)
    except Exception:  # malformed files from third-party parsers
        log.warning('Could not extract text from a %s upload', ext, exc_info=DEBUG)
    return name, ''


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def score_label(score):
    if score >= 35:
        return 'Strong'
    if score >= 20:
        return 'Moderate'
    return 'Weak'


def rank_resumes(job_description, resumes, names):
    vectorizer = TfidfVectorizer(stop_words='english')
    matrix = vectorizer.fit_transform([job_description] + resumes)
    terms = vectorizer.get_feature_names_out()

    similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    # The job's most important terms by TF-IDF weight (skip pure numbers like "2024")
    jd_row = matrix[0].toarray().ravel()
    jd_top = [i for i in jd_row.argsort()[::-1]
              if jd_row[i] > 0 and not terms[i].isdigit()][:JD_KEY_TERMS]
    jd_terms = [terms[i] for i in jd_top]

    top = similarities.argsort()[::-1][:TOP_N]
    results = []
    for idx in top:
        row = matrix[idx + 1].toarray().ravel()
        score = float(similarities[idx] * 100)
        text = resumes[idx]
        results.append({
            'name': names[idx],
            'ext': names[idx].rsplit('.', 1)[-1],
            'score': score,
            'label': score_label(score),
            'matched': [terms[i] for i in jd_top if row[i] > 0],
            'missing': [terms[i] for i in jd_top if row[i] == 0][:8],
            'words': len(text.split()),
            'content': text[:1500] + ('…' if len(text) > 1500 else ''),
        })
    return results, jd_terms


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/learn')
def learn():
    return render_template('learn.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.static_folder, 'icons'), 'favicon.ico',
                               mimetype='image/vnd.microsoft.icon', max_age=86400)


@app.route('/robots.txt')
def robots():
    return app.response_class('User-agent: *\nAllow: /\nDisallow: /match\n', mimetype='text/plain')


def form_error(message, status=400, keep_text=True):
    """Re-show the form with an error, keeping the pasted job description when it's safe to read."""
    flash(message)
    jd_text = request.form.get('jd-text', '')[:MAX_TEXT_CHARS] if keep_text else ''
    return render_template('match.html', jd_text=jd_text), status


@app.route('/match', methods=['GET', 'POST'])
def match_resumes():
    if request.method == 'GET':
        return render_template('match.html')

    # Job description: file first, pasted text as fallback
    job_description = ''
    jd_file = request.files.get('jd-file')
    if jd_file and jd_file.filename:
        if not allowed_file(jd_file.filename):
            return form_error('The job description file must be PDF, DOCX or TXT.')
        _, job_description = read_upload(jd_file, 'job-description')
        if not job_description:
            return form_error("We couldn't read any text from the job description file. Try pasting it instead.")
    if not job_description:
        job_description = request.form.get('jd-text', '').strip()[:MAX_TEXT_CHARS]
    if not job_description:
        return form_error('Add a job description: paste the text or upload a file.')

    # Resumes
    uploads = [f for f in request.files.getlist('resumes-file') if f and f.filename]
    if len(uploads) > MAX_RESUMES:
        return form_error(f'Upload at most {MAX_RESUMES} resumes at a time.')

    resumes, names, skipped = [], [], 0
    for n, file in enumerate(uploads, start=1):
        if not allowed_file(file.filename):
            skipped += 1
            continue
        name, text = read_upload(file, f'resume-{n}')
        if text:
            resumes.append(text)
            names.append(name)
        else:
            skipped += 1

    if not resumes:
        if skipped:
            return form_error("We couldn't read text from any of the resumes. "
                              "Scanned (image-only) or password-protected PDFs aren't supported.")
        return form_error('Add at least one resume to compare.')

    try:
        results, jd_terms = rank_resumes(job_description, resumes, names)
    except ValueError:
        # Raised by TfidfVectorizer when every word is a stop word
        return form_error('There was not enough meaningful text to compare. Try a longer job description.')

    return render_template(
        'results.html',
        job_description=job_description[:1200] + ('…' if len(job_description) > 1200 else ''),
        results=results,
        jd_terms=jd_terms,
        total=len(resumes),
        skipped=skipped,
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def error_page(code, title, message):
    return render_template('error.html', code=code, title=title, message=message), code


@app.errorhandler(400)
def bad_request(_):
    return error_page(400, 'Bad request', "The request couldn't be understood. Please try again.")


@app.errorhandler(404)
def not_found(_):
    return error_page(404, 'Page not found', "The page you're looking for doesn't exist or has moved.")


@app.errorhandler(405)
def method_not_allowed(_):
    return error_page(405, 'Not allowed', "That action isn't available on this page.")


@app.errorhandler(413)
def too_large(_):
    # The body was refused, so the form can't be read again here
    return form_error('Those files are too large. Keep the total upload under 16 MB.', 413, keep_text=False)


@app.errorhandler(500)
def server_error(_):
    return error_page(500, 'Something went wrong', 'An unexpected error occurred. Please try again.')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=DEBUG)
