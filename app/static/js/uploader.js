import { ApiClient } from './api.js';

export const Uploader = {
  init(onUploadSuccess) {
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('file-input');
    const modal = document.getElementById('upload-modal');

    if (!dropzone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
      }, false);
    });

    dropzone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) this.handleFile(files[0], onUploadSuccess);
    });

    dropzone.addEventListener('click', (e) => {
      if (e.target.tagName !== 'INPUT') fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        this.handleFile(e.target.files[0], onUploadSuccess);
      }
    });
  },

  async handleFile(file, onUploadSuccess) {
    const progressContainer = document.getElementById('upload-progress-container');
    const progressBar = document.getElementById('upload-progress-bar');
    const stageLabel = document.getElementById('upload-stage-label');
    const stagePct = document.getElementById('upload-stage-pct');
    const statusText = document.getElementById('upload-status-text');

    if (progressContainer) progressContainer.style.display = 'block';

    const stages = [
      { pct: 25, label: '1/4: Ingesting Raw Dataset...', status: `Reading ${file.name}` },
      { pct: 55, label: '2/4: Profiling Data Quality & Outliers...', status: 'Computing column nullability & metrics' },
      { pct: 80, label: '3/4: Converting to High-Speed Parquet...', status: 'Optimizing DuckDB analytical storage' },
      { pct: 95, label: '4/4: Synthesizing Semantic Model & KPIs...', status: 'Generating dynamic executive layout' },
    ];

    let currentStage = 0;
    const interval = setInterval(() => {
      if (currentStage < stages.length) {
        const s = stages[currentStage];
        if (progressBar) progressBar.style.width = `${s.pct}%`;
        if (stagePct) stagePct.innerText = `${s.pct}%`;
        if (stageLabel) stageLabel.innerText = s.label;
        if (statusText) statusText.innerText = s.status;
        currentStage++;
      }
    }, 450);

    try {
      const res = await ApiClient.uploadDataset(file);
      clearInterval(interval);
      if (progressBar) progressBar.style.width = '100%';
      if (stagePct) stagePct.innerText = '100%';
      if (stageLabel) stageLabel.innerText = 'Complete!';
      if (statusText) statusText.innerText = 'Dashboard hydrated successfully!';

      setTimeout(() => {
        document.getElementById('upload-modal').classList.remove('active');
        if (progressContainer) progressContainer.style.display = 'none';
        if (onUploadSuccess) onUploadSuccess(res.dataset_id);
      }, 700);
    } catch (err) {
      clearInterval(interval);
      alert(`Upload error: ${err.message}`);
      if (progressContainer) progressContainer.style.display = 'none';
    }
  }
};
