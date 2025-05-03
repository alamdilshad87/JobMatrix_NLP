from flask import Flask, request, render_template, redirect, url_for, flash
import os
import docx2txt
import PyPDF2
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='template')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your-secret-key-here'

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configure allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        logging.error(f"PDF extraction error: {e}")
        return ""


def extract_text_from_docx(file_path):
    try:
        return docx2txt.process(file_path).strip()
    except Exception as e:
        logging.error(f"DOCX extraction error: {e}")
        return ""


def extract_text_from_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except Exception as e:
        logging.error(f"TXT extraction error: {e}")
        return ""


def extract_text(file_path):
    ext = file_path.split('.')[-1].lower()
    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ['docx', 'doc']:
        return extract_text_from_docx(file_path)
    elif ext == 'txt':
        return extract_text_from_txt(file_path)
    return ""


@app.route('/')
def home():
    # Serve the main landing page
    return render_template('index.html')

@app.route('/learn')
def learn():
    # Serve the learning page
    return render_template('learn.html')

@app.route('/about')
def about():
    # Serve the About page
    return render_template('about.html')

@app.route('/match', methods=['GET', 'POST'])
def match_resumes():
    if request.method == 'POST':
        # Handle job description (file or text)
        job_description = ""

        # Check file upload first
        if 'jd-file' in request.files:
            file = request.files['jd-file']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                job_description = extract_text(filepath)
                os.remove(filepath)  # Remove file after processing

        # Fall back to text input if no file or empty result
        if not job_description.strip():
            job_description = request.form.get('jd-text', '').strip()

        if not job_description:
            flash('Please provide a job description', 'error')
            return redirect(url_for('match_resumes'))

        # Process resumes
        if 'resumes-file' not in request.files:
            flash('No resume files uploaded', 'error')
            return redirect(url_for('match_resumes'))

        resume_files = request.files.getlist('resumes-file')
        resumes = []
        resume_names = []

        for file in resume_files:
            if file.filename == '':
                continue

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                text = extract_text(filepath)
                os.remove(filepath)  # Remove file after processing

                if text.strip():
                    resumes.append(text)
                    resume_names.append(filename)

        if not resumes:
            flash('No valid resumes were processed', 'error')
            return redirect(url_for('match_resumes'))

        # Perform matching
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform([job_description] + resumes)

            cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

            # Get top 5 matches (or fewer if there aren't 5 resumes)
            num_matches = min(5, len(resumes))
            top_indices = cosine_similarities.argsort()[-num_matches:][::-1]
            results = []

            for idx in top_indices:
                # Calculate match percentage
                match_score = cosine_similarities[idx] * 100

                # Get a preview of the content (first 300 characters)
                content_preview = resumes[idx][:300] + ('...' if len(resumes[idx]) > 300 else '')

                results.append({
                    'name': resume_names[idx],
                    'score': f"{match_score:.1f}%",
                    'content': content_preview
                })

            return render_template('results.html',
                                   job_description=job_description[:500] + (
                                       '...' if len(job_description) > 500 else ''),
                                   results=results)

        except Exception as e:
            logging.error(f"Matching error: {e}")
            flash('An error occurred during processing', 'error')
            return redirect(url_for('match_resumes'))

    # GET request - show the matching form
    return render_template('match.html')


if __name__ == '__main__':
    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    app.run(debug=True)