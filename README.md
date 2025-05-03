# 💼 JobMatrix - Resume Matcher using NLP

A powerful resume matching system using **TF-IDF** and **Cosine Similarity** to help recruiters instantly find the best candidates. 🔍

This project simplifies recruitment by comparing resumes against a job description and scoring them based on content similarity.

---

## 🧠 What It Does

✨ Automatically extracts and analyzes content from resumes (PDF, DOCX, TXT)  
📄 Matches them against a Job Description using **NLP**  
⚡ Shows the **Top 5 Most Relevant** resumes with match %  
🎯 Reduces manual screening time  
✅ Built with Flask + scikit-learn  
🌐 Deployed on [Render](https://render.com)

---

## 📁 Project Structure

```bash
JobMatrix_NLP/
├── static/
│   └── images/           # Profile/branding images
├── template/             # All frontend HTML pages
│   ├── index.html
│   ├── match.html
│   ├── learn.html
│   ├── results.html
│   ├── about.html
├── uploads/              # Temporary resume/job files
├── app.py                # Flask backend application
├── requirements.txt      # All Python dependencies
└── Resumes_NLP.zip       # Sample resumes (optional)
```

---

## 🛠️ Features & Tech Stack

| Feature                  | Tech                      |
|--------------------------|---------------------------|
| 📝 Resume & JD Input      | Upload or type text       |
| 🧹 Preprocessing           | Lowercase, stop word removal |
| 🔢 TF-IDF Vectorization    | `TfidfVectorizer()`       |
| 📐 Cosine Similarity       | `cosine_similarity()`     |
| 💻 Web Framework           | Flask                     |
| 🧪 Resume Parsing          | `docx2txt`, `PyPDF2`       |
| 🛑 Allowed Formats         | `.pdf`, `.docx`, `.txt`, `.doc` |
| 🚀 Deployment              | Render                    |
| 🧠 Built For               | PyCharm (with venv)       |

---

## 🚀 How to Run 

### ✅ Prerequisites

- PyCharm or any other platforms 
- Python 3.8+ 

### 🔧 Step-by-Step Setup

1. **Clone the Repository**

```bash
git clone https://github.com/your-username/JobMatrix_NLP.git
cd JobMatrix_NLP
```

2. **Open in PyCharm**

> File > Open > Select `JobMatrix_NLP` folder

3. **Create Virtual Environment**

> PyCharm auto-detects & creates `venv` (recommended)

4. **Install Dependencies**

```bash
pip install -r requirements.txt
```

5. **Run the App**

```bash
python app.py
```

6. **Visit in Browser**

```
http://localhost:5000/
```

---

## 🧪 Demo Flow

- **Home Page** → Learn, About, or Jump to Resume Matching  
- **Match Page** → Upload a JD (or paste text) + Resumes  
- **See Results** → Top 5 resumes ranked with %  
- **Learn Page** → Understand the science behind the tool  
- **About Page** → Know about the contributors

---

## ✍️ Sample Input Formats

- **JD Upload**: PDF, TXT, DOCX  
- **Resume Upload**: Upload 1 or more resumes in accepted formats  
- **Fallback**: You can also **paste** the JD manually if you don’t have a file

---

## 📐 Formula Used

### 🔢 TF-IDF (Term Frequency – Inverse Document Frequency)

The **TF-IDF** score is calculated as:

$$
\text{TF-IDF}(t, d) = \text{TF}(t, d) \times \log\left(\frac{N}{\text{DF}(t)}\right)
$$

Where:  
- **t** = term  
- **d** = document  
- **N** = total number of documents  
- **DF(t)** = number of documents containing the term **t**

---

### 🔗 Cosine Similarity

Used to measure the **angle between vectors** of the Job Description and Resume — closer the angle, higher the match.

$$
\text{Similarity} = \cos(\theta) = \frac{A \cdot B}{\|A\| \times \|B\|}
$$

Where:

A · B is the dot product of vectors A and B

|A| is the magnitude (length) of vector A

|B| is the magnitude (length) of vector B

The output value ranges from 0 (no similarity) to 1 (perfect similarity)

---

## 🧠 Future Enhancements

- ✅ User login/authentication  
- ✅ Admin dashboard  
- ✅ Save history to database (MongoDB / PostgreSQL)  
- ✅ Add NLP semantic matching (with BERT)  
- ✅ Mobile-responsive UI  



---

## 👨‍💻 Contributors

**MD Dilshad Alam**    
📧 [dilshadand@gmail.com]  
🌐 [https://www.linkedin.com/in/alamdilshad87/]

---

## 📸 UI Preview

---

## 📦 Sample Resume Files

Check `Resumes_NLP.zip` inside the repo to test your first matching!
