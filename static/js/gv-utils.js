/**
 * GeoView Suite - 공통 유틸리티 v1.0
 * Toast 알림, 로딩 스피너, 삭제 확인 모달, 키보드 단축키
 */

/* ────────────────────────────────────────
   1. Toast 알림
   사용: gvToast('저장되었습니다', 'success')
   타입: success, error, warning, info
   ──────────────────────────────────────── */
(function() {
    // Toast 컨테이너 자동 생성
    if (!document.getElementById('gv-toast-container')) {
        const container = document.createElement('div');
        container.id = 'gv-toast-container';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
})();

function gvToast(message, type = 'info', duration = 3000) {
    const icons = {
        success: 'bi-check-circle-fill',
        error: 'bi-x-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill'
    };
    const colors = {
        success: '#198754', error: '#dc3545',
        warning: '#fd7e14', info: '#0d6efd'
    };
    const id = 'toast-' + Date.now();
    const html = `
    <div id="${id}" class="toast align-items-center border-0 mb-2" role="alert"
         style="background:var(--gv-navy,#1a1d23);border-left:4px solid ${colors[type]}!important;min-width:300px;">
        <div class="d-flex">
            <div class="toast-body d-flex align-items-center gap-2" style="color:var(--gv-text,#e0e0e0);">
                <i class="bi ${icons[type] || icons.info}" style="color:${colors[type]};font-size:1.1em;"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    </div>`;
    const container = document.getElementById('gv-toast-container');
    container.insertAdjacentHTML('beforeend', html);
    const el = document.getElementById(id);
    const toast = new bootstrap.Toast(el, { delay: duration });
    toast.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
}


/* ────────────────────────────────────────
   2. 로딩 스피너 오버레이
   사용: gvSpinner.show('처리 중...') / gvSpinner.hide()
   ──────────────────────────────────────── */
const gvSpinner = {
    _el: null,
    _init() {
        if (this._el) return;
        const overlay = document.createElement('div');
        overlay.id = 'gv-spinner-overlay';
        overlay.innerHTML = `
            <div style="position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:10000;
                 display:none;align-items:center;justify-content:center;flex-direction:column;gap:16px;">
                <div class="spinner-border text-primary" style="width:3rem;height:3rem;" role="status"></div>
                <span id="gv-spinner-msg" style="color:#e0e0e0;font-size:.95rem;">처리 중...</span>
            </div>`;
        document.body.appendChild(overlay);
        this._el = overlay.firstElementChild;
    },
    show(msg = '처리 중...') {
        this._init();
        document.getElementById('gv-spinner-msg').textContent = msg;
        this._el.style.display = 'flex';
    },
    hide() {
        if (this._el) this._el.style.display = 'none';
    }
};


/* ────────────────────────────────────────
   3. 삭제 확인 모달
   사용: gvConfirmDelete('프로젝트 A', () => { ...삭제로직... })
   ──────────────────────────────────────── */
(function() {
    if (document.getElementById('gv-delete-modal')) return;
    const modal = document.createElement('div');
    modal.innerHTML = `
    <div class="modal fade" id="gv-delete-modal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content" style="background:var(--gv-navy,#1a1d23);border:1px solid var(--gv-border,#2d3748);">
                <div class="modal-header border-0">
                    <h6 class="modal-title" style="color:var(--gv-text,#e0e0e0);">
                        <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>삭제 확인
                    </h6>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="color:var(--gv-text-muted,#a0aec0);">
                    <span id="gv-delete-msg"></span>
                </div>
                <div class="modal-footer border-0">
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">취소</button>
                    <button type="button" class="btn btn-sm btn-danger" id="gv-delete-confirm-btn">
                        <i class="bi bi-trash3 me-1"></i>삭제
                    </button>
                </div>
            </div>
        </div>
    </div>`;
    document.body.appendChild(modal.firstElementChild);
})();

let _gvDeleteCallback = null;

function gvConfirmDelete(itemName, onConfirm) {
    document.getElementById('gv-delete-msg').innerHTML =
        `<strong>"${itemName}"</strong>을(를) 삭제하시겠습니까?<br><small class="text-danger">이 작업은 되돌릴 수 없습니다.</small>`;
    _gvDeleteCallback = onConfirm;
    const modal = new bootstrap.Modal(document.getElementById('gv-delete-modal'));
    modal.show();
}

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('gv-delete-confirm-btn');
    if (btn) {
        btn.addEventListener('click', () => {
            bootstrap.Modal.getInstance(document.getElementById('gv-delete-modal'))?.hide();
            if (typeof _gvDeleteCallback === 'function') _gvDeleteCallback();
            _gvDeleteCallback = null;
        });
    }
});


/* ────────────────────────────────────────
   4. 키보드 단축키
   Ctrl+Enter: 현재 폼 제출
   Esc: 모달 닫기
   ──────────────────────────────────────── */
document.addEventListener('keydown', function(e) {
    // Ctrl+Enter: submit focused form
    if (e.ctrlKey && e.key === 'Enter') {
        const form = document.activeElement?.closest('form');
        if (form) {
            e.preventDefault();
            form.requestSubmit();
        }
    }
});


/* ────────────────────────────────────────
   5. Flash 메시지 자동 사라짐 (5초)
   ──────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.alert-dismissible').forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert?.close();
        }, 5000);
    });
});


/* ────────────────────────────────────────
   6. 폼 제출 시 스피너 + 중복 방지
   사용: <form data-gv-submit="저장 중...">
   ──────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form[data-gv-submit]').forEach(form => {
        form.addEventListener('submit', function() {
            const msg = this.dataset.gvSubmit || '처리 중...';
            gvSpinner.show(msg);
            const btns = this.querySelectorAll('button[type="submit"], input[type="submit"]');
            btns.forEach(b => b.disabled = true);
        });
    });
});
