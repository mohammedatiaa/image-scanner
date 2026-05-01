document.addEventListener('DOMContentLoaded', () => {
    // ===== Theme Toggle =====
    const themeToggle = document.getElementById('theme-toggle');
    const iconSun = document.getElementById('icon-sun');
    const iconMoon = document.getElementById('icon-moon');

    function applyTheme(dark) {
        if (dark) {
            document.documentElement.classList.add('dark');
            iconSun.classList.remove('icon-hidden');
            iconMoon.classList.add('icon-hidden');
        } else {
            document.documentElement.classList.remove('dark');
            iconMoon.classList.remove('icon-hidden');
            iconSun.classList.add('icon-hidden');
        }
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
    function showToast(message, duration = 2500) {
        clearTimeout(toastTimeout);
        toastEl.textContent = message;
        toastEl.classList.add('show');
        toastTimeout = setTimeout(() => toastEl.classList.remove('show'), duration);
    }

    // ===== DOM Elements =====
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadCard = document.getElementById('upload-card');
    const resultCard = document.getElementById('result-card');
    const uploadSpinner = document.getElementById('upload-spinner');
    const originalImage = document.getElementById('original-image');
    const scannedImage = document.getElementById('scanned-image');
    const downloadImageBtn = document.getElementById('download-image-btn');
    const generatePdfBtn = document.getElementById('generate-pdf-btn');
    const pdfSpinner = document.getElementById('pdf-spinner');
    const pdfResult = document.getElementById('pdf-result');
    const downloadPdfBtn = document.getElementById('download-pdf-btn');
    const extractTextBtn = document.getElementById('extract-text-btn');
    const ocrSpinner = document.getElementById('ocr-spinner');
    const ocrResult = document.getElementById('ocr-result');
    const ocrText = document.getElementById('ocr-text');
    const copyTextBtn = document.getElementById('copy-text-btn');
    const downloadTextBtn = document.getElementById('download-text-btn');
    const ocrLang = document.getElementById('ocr-lang');
    const scanAgainBtn = document.getElementById('scan-again-btn');
    const effectBadgeText = document.getElementById('effect-badge-text');
    const rescanSpinner = document.getElementById('rescan-spinner');

    let scannedImagePath = '';
    let originalImagePath = '';
    let currentEffect = 'magic';
    let ocrBlobUrl = '';

    // ===== Effect Selector (Upload Card) =====
    const uploadEffectBtns = uploadCard.querySelectorAll('.effect-btn');
    uploadEffectBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            uploadEffectBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentEffect = btn.dataset.effect;
        });
    });

    // ===== Effect Selector (Result Card - Rescan) =====
    const rescanEffectBtns = document.querySelectorAll('#rescan-effects .effect-btn');
    rescanEffectBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const newEffect = btn.dataset.effect;
            if (newEffect === currentEffect) return;

            rescanEffectBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentEffect = newEffect;

            // Re-process
            rescanSpinner.classList.add('visible');
            try {
                const response = await fetch('/rescan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        original_image_url: originalImagePath,
                        effect: currentEffect
                    }),
                });
                if (!response.ok) throw new Error('Rescan failed');

                const result = await response.json();
                scannedImagePath = result.scanned_image_url;
                scannedImage.src = scannedImagePath + '?t=' + Date.now();
                downloadImageBtn.href = scannedImagePath;
                updateEffectBadge();
                showToast('Effect applied successfully!');

                // Reset PDF & OCR since image changed
                pdfResult.classList.remove('visible');
                ocrResult.classList.remove('visible');

            } catch (error) {
                console.error('Rescan error:', error);
                showToast('Failed to apply effect');
            } finally {
                rescanSpinner.classList.remove('visible');
            }
        });
    });

    function updateEffectBadge() {
        const labels = { magic: '✨ Magic Scan', enhanced: '🎨 Enhanced', bw: '📝 Black & White', original: '📷 Original' };
        effectBadgeText.textContent = labels[currentEffect] || 'Magic Scan';
    }

    // ===== File Upload =====
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

    // Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false);
    });
    ['dragenter', 'dragover'].forEach(evt => {
        dropZone.addEventListener(evt, () => dropZone.classList.add('dragging', 'pulse'), false);
    });
    ['dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, () => dropZone.classList.remove('dragging', 'pulse'), false);
    });
    dropZone.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files), false);

    // Paste
    const imageExtensionPattern = /\.(png|jpe?g|gif|bmp|webp|tiff?)$/i;
    function isLikelyImage(file) {
        if (!file) return false;
        if (file.type && file.type.startsWith('image/')) return true;
        return Boolean(file.name && imageExtensionPattern.test(file.name));
    }

    document.addEventListener('paste', (e) => {
        const cd = e.clipboardData;
        if (!cd) return;
        let images = [];
        if (cd.files && cd.files.length) {
            images = Array.from(cd.files).filter(isLikelyImage);
        } else if (cd.items) {
            images = Array.from(cd.items)
                .filter(item => item.kind === 'file')
                .map(item => item.getAsFile())
                .filter(isLikelyImage);
        }
        if (images.length) {
            e.preventDefault();
            handleFiles(images);
        }
    });

    async function handleFiles(files) {
        const file = files[0];
        if (!isLikelyImage(file)) {
            showToast('Please upload an image file');
            return;
        }

        uploadSpinner.classList.add('visible');
        dropZone.style.display = 'none';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('effect', currentEffect);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                let msg = 'Upload failed';
                try {
                    const errData = await response.json();
                    msg = errData.detail || errData.message || msg;
                } catch {}
                throw new Error(msg);
            }

            const result = await response.json();
            scannedImagePath = result.scanned_image_url;
            originalImagePath = result.original_image_url;

            scannedImage.src = scannedImagePath;
            originalImage.src = originalImagePath;
            downloadImageBtn.href = scannedImagePath;

            // Sync rescan effect buttons
            rescanEffectBtns.forEach(b => {
                b.classList.toggle('active', b.dataset.effect === currentEffect);
            });
            updateEffectBadge();

            // Reset sub-results
            pdfResult.classList.remove('visible');
            ocrResult.classList.remove('visible');
            ocrText.value = '';
            if (ocrBlobUrl) { URL.revokeObjectURL(ocrBlobUrl); ocrBlobUrl = ''; }
            downloadTextBtn.href = '#';

            // Transition: upload → result
            uploadCard.classList.add('zoom-out');
            uploadCard.addEventListener('animationend', function handler() {
                uploadCard.removeEventListener('animationend', handler);
                uploadCard.style.display = 'none';
                uploadCard.classList.remove('zoom-out');
                resultCard.classList.add('visible', 'zoom-in');
            });

        } catch (error) {
            console.error('Upload error:', error);
            showToast(error.message || 'Upload failed');
            uploadSpinner.classList.remove('visible');
            dropZone.style.display = '';
        }
    }

    // ===== Generate PDF =====
    generatePdfBtn.addEventListener('click', async () => {
        pdfSpinner.classList.add('visible');
        generatePdfBtn.disabled = true;

        try {
            const response = await fetch('/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scanned_image_path: scannedImagePath }),
            });
            if (!response.ok) throw new Error('PDF conversion failed');

            const result = await response.json();
            downloadPdfBtn.href = result.pdf_url;
            pdfResult.classList.add('visible');
            showToast('PDF generated successfully!');
        } catch (error) {
            console.error('PDF error:', error);
            showToast('PDF generation failed');
        } finally {
            pdfSpinner.classList.remove('visible');
            generatePdfBtn.disabled = false;
        }
    });

    // ===== Extract Text (OCR) =====
    extractTextBtn.addEventListener('click', async () => {
        if (!scannedImagePath) {
            showToast('Please upload an image first');
            return;
        }

        ocrSpinner.classList.add('visible');
        extractTextBtn.disabled = true;

        try {
            const response = await fetch('/ocr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    scanned_image_path: scannedImagePath,
                    lang: ocrLang ? ocrLang.value : 'eng'
                }),
            });

            if (!response.ok) {
                let msg = 'Text extraction failed';
                try {
                    const errData = await response.json();
                    msg = errData.detail || errData.message || msg;
                } catch {}
                throw new Error(msg);
            }

            const result = await response.json();
            const text = result.text || '';
            ocrText.value = text.trim() || 'No text detected.';
            ocrResult.classList.add('visible');

            const blob = new Blob([ocrText.value], { type: 'text/plain;charset=utf-8' });
            if (ocrBlobUrl) URL.revokeObjectURL(ocrBlobUrl);
            ocrBlobUrl = URL.createObjectURL(blob);
            downloadTextBtn.href = ocrBlobUrl;
            downloadTextBtn.download = 'extracted-text.txt';

            showToast('Text extracted successfully!');
        } catch (error) {
            console.error('OCR error:', error);
            showToast(error.message || 'Text extraction failed');
        } finally {
            ocrSpinner.classList.remove('visible');
            extractTextBtn.disabled = false;
        }
    });

    // ===== Copy Text =====
    copyTextBtn.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(ocrText.value || '');
            showToast('Copied to clipboard!');
        } catch {
            showToast('Could not copy text');
        }
    });

    // ===== Scan Again =====
    scanAgainBtn.addEventListener('click', () => {
        resultCard.classList.add('zoom-out');
        resultCard.addEventListener('animationend', function handler() {
            resultCard.removeEventListener('animationend', handler);
            resultCard.classList.remove('visible', 'zoom-in', 'zoom-out');

            // Reset upload card
            uploadSpinner.classList.remove('visible');
            dropZone.style.display = '';
            uploadCard.style.display = '';
            uploadCard.classList.add('zoom-in');
            fileInput.value = '';
        });
    });
});
