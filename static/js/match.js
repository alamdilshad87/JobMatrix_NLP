(function () {
    var ALLOWED = ['pdf', 'docx', 'txt'];
    var form = document.getElementById('match-form');
    var jdText = document.getElementById('jd-text');
    var jdFile = document.getElementById('jd-file');
    var resumesInput = document.getElementById('resumes-file');
    var resumeList = document.getElementById('resume-list');
    var jdList = document.getElementById('jd-list');
    var resumeCount = document.getElementById('resume-count');
    var resumes = new DataTransfer();

    function ext(name) { return (name.split('.').pop() || '').toLowerCase(); }
    function size(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return Math.round(bytes / 1024) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }
    function showError(msg) {
        var existing = document.querySelector('.alert');
        if (existing) existing.remove();
        var div = document.createElement('div');
        div.className = 'alert';
        div.setAttribute('role', 'alert');
        var inner = document.createElement('div');
        inner.textContent = msg;
        div.appendChild(inner);
        form.parentNode.insertBefore(div, form);
        div.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    function fileRow(file, onRemove) {
        var li = document.createElement('li');
        li.className = 'file-item';
        li.innerHTML = '<span class="file-ext"></span><span class="file-name"></span><span class="file-size"></span><button type="button" class="file-remove">×</button>';
        li.querySelector('.file-ext').textContent = ext(file.name);
        li.querySelector('.file-name').textContent = file.name;
        li.querySelector('.file-name').title = file.name;
        li.querySelector('.file-size').textContent = size(file.size);
        li.querySelector('.file-remove').setAttribute('aria-label', 'Remove ' + file.name);
        li.querySelector('.file-remove').addEventListener('click', onRemove);
        return li;
    }

    // Paste / Upload
    var tabs = { paste: document.getElementById('tab-paste'), upload: document.getElementById('tab-upload') };
    var panels = { paste: document.getElementById('jd-paste'), upload: document.getElementById('jd-upload') };
    function selectTab(name) {
        Object.keys(tabs).forEach(function (k) {
            tabs[k].setAttribute('aria-selected', k === name ? 'true' : 'false');
            panels[k].hidden = k !== name;
        });
    }
    tabs.paste.addEventListener('click', function () { selectTab('paste'); });
    tabs.upload.addEventListener('click', function () { selectTab('upload'); });

    function countWords() {
        var t = jdText.value.trim();
        document.getElementById('jd-count').textContent = t ? t.split(/\s+/).length : 0;
    }
    jdText.addEventListener('input', countWords);
    countWords();

    function renderJd() {
        jdList.innerHTML = '';
        if (jdFile.files.length) jdList.appendChild(fileRow(jdFile.files[0], function () { jdFile.value = ''; renderJd(); }));
    }
    jdFile.addEventListener('change', function () {
        if (jdFile.files.length && ALLOWED.indexOf(ext(jdFile.files[0].name)) === -1) {
            showError('"' + jdFile.files[0].name + '" is not a supported format. Use PDF, DOCX or TXT.');
            jdFile.value = '';
        }
        renderJd();
    });

    // Keep a running list so files can be added in several goes and removed
    function renderResumes() {
        resumeList.innerHTML = '';
        Array.prototype.forEach.call(resumes.files, function (file, i) {
            resumeList.appendChild(fileRow(file, function () {
                var next = new DataTransfer();
                Array.prototype.forEach.call(resumes.files, function (f, j) { if (j !== i) next.items.add(f); });
                resumes = next;
                resumesInput.files = resumes.files;
                renderResumes();
            }));
        });
        var n = resumes.files.length;
        resumeCount.textContent = n ? n + (n === 1 ? ' file' : ' files') : 'None yet';
    }
    resumesInput.addEventListener('change', function () {
        var rejected = [];
        var existing = Array.prototype.map.call(resumes.files, function (f) { return f.name + f.size; });
        Array.prototype.forEach.call(resumesInput.files, function (f) {
            if (ALLOWED.indexOf(ext(f.name)) === -1) { rejected.push(f.name); return; }
            if (existing.indexOf(f.name + f.size) === -1) resumes.items.add(f);
        });
        resumesInput.files = resumes.files;
        renderResumes();
        if (rejected.length) showError('Skipped unsupported file(s): ' + rejected.join(', ') + '. Use PDF, DOCX or TXT.');
    });

    ['jd-drop', 'resume-drop'].forEach(function (id) {
        var zone = document.getElementById(id);
        ['dragenter', 'dragover'].forEach(function (e) { zone.addEventListener(e, function () { zone.classList.add('dragover'); }); });
        ['dragleave', 'drop'].forEach(function (e) { zone.addEventListener(e, function () { zone.classList.remove('dragover'); }); });
    });

    form.addEventListener('submit', function (e) {
        if (!jdText.value.trim() && !jdFile.files.length) { e.preventDefault(); showError('Add a job description: paste the text or upload a file.'); return; }
        if (!resumes.files.length) { e.preventDefault(); showError('Add at least one resume to compare.'); return; }
        if (resumes.files.length > 50) { e.preventDefault(); showError('Upload at most 50 resumes at a time.'); return; }
        var total = Array.prototype.reduce.call(resumes.files, function (n, f) { return n + f.size; }, jdFile.files.length ? jdFile.files[0].size : 0);
        if (total > 16 * 1048576) { e.preventDefault(); showError('Those files add up to ' + size(total) + '. Keep the total under 16 MB.'); return; }
        document.getElementById('submit-btn').disabled = true;
        document.getElementById('submit-label').textContent = 'Ranking…';
        document.getElementById('progress').classList.add('run');
    });

    window.addEventListener('pageshow', function (e) { if (e.persisted) window.location.reload(); });
})();
