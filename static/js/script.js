document.addEventListener('DOMContentLoaded', () => {
    // ===== Theme Toggle =====
    const themeToggle = document.getElementById('theme-toggle');
    const iconSun = document.getElementById('icon-sun');
    const iconMoon = document.getElementById('icon-moon');

    function applyTheme(dark) {
        document.documentElement.classList.toggle('dark', dark);
        iconSun.classList.toggle('icon-hidden', !dark);
        iconMoon.classList.toggle('icon-hidden', dark);
    }

    const savedTheme = localStorage.getItem('color-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(savedTheme === 'dark' || (!savedTheme && prefersDark));

    themeToggle.addEventListener('click', () => {
        const isDark = document.documentElement.classList.contains('dark');
        applyTheme(!isDark);
        localStorage.setItem('color-theme', isDark ? 'light' : 'dark');
    });

    // ===== Toast =====
    const toastEl = document.getElementById('toast');
    let toastTimeout;
    function showToast(msg, ms = 2500) {
        clearTimeout(toastTimeout);
        toastEl.textContent = msg;
        toastEl.classList.add('show');
        toastTimeout = setTimeout(() => toastEl.classList.remove('show'), ms);
    }

    // ===== DOM =====
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadCard = document.getElementById('upload-card');
    const resultCard = document.getElementById('result-card');
    const uploadSpinner = document.getElementById('upload-spinner');
    const originalImage = document.getElementById('original-image');
    const scannedImage = document.getElementById('scanned-image');
    const downloadBtn = document.getElementById('download-image-btn');
    const scanAgainBtn = document.getElementById('scan-again-btn');

    // ===== File Upload =====
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

    // Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt =>
        dropZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); })
    );
    ['dragenter', 'dragover'].forEach(evt =>
        dropZone.addEventListener(evt, () => dropZone.classList.add('dragging', 'pulse'))
    );
    ['dragleave', 'drop'].forEach(evt =>
        dropZone.addEventListener(evt, () => dropZone.classList.remove('dragging', 'pulse'))
    );
    dropZone.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files));

    // Paste
    document.addEventListener('paste', (e) => {
        const files = e.clipboardData?.files;
        if (files?.length) { e.preventDefault(); handleFiles(files); }
    });

    async function handleFiles(files) {
        const file = files[0];
        if (!file || !file.type.startsWith('image/')) {
            showToast('Please upload an image file');
            return;
        }

        uploadSpinner.classList.add('visible');
        dropZone.style.display = 'none';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/upload', { method: 'POST', body: formData });
            if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');

            const data = await res.json();
            scannedImage.src = data.scanned_image_url;
            originalImage.src = data.original_image_url;
            downloadBtn.href = data.scanned_image_url;

            uploadCard.classList.add('zoom-out');
            uploadCard.addEventListener('animationend', function handler() {
                uploadCard.removeEventListener('animationend', handler);
                uploadCard.style.display = 'none';
                uploadCard.classList.remove('zoom-out');
                resultCard.classList.add('visible', 'zoom-in');
            });
        } catch (err) {
            console.error(err);
            showToast(err.message || 'Upload failed');
            uploadSpinner.classList.remove('visible');
            dropZone.style.display = '';
        }
    }

    // ===== Scan Again =====
    scanAgainBtn.addEventListener('click', () => {
        resultCard.classList.add('zoom-out');
        resultCard.addEventListener('animationend', function handler() {
            resultCard.removeEventListener('animationend', handler);
            resultCard.classList.remove('visible', 'zoom-in', 'zoom-out');
            uploadSpinner.classList.remove('visible');
            dropZone.style.display = '';
            uploadCard.style.display = '';
            uploadCard.classList.add('zoom-in');
            fileInput.value = '';
        });
    });
});
