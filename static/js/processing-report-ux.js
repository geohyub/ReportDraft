(function () {
    const STORAGE_KEYS = {
        autosave: "processing-report-draft.autosave.v2",
        presets: "processing-report-draft.presets.v1",
    };

    let autosaveTimer = null;
    let htmlPreviewTimer = null;
    let revisionCatalog = [];
    let lastRenderedFlow = null;

    function escapeHtml(value) {
        if (value === null || value === undefined) return "";
        const div = document.createElement("div");
        div.textContent = String(value);
        return div.innerHTML;
    }

    function readStorage(key, fallback) {
        try {
            const raw = window.localStorage.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (err) {
            return fallback;
        }
    }

    function writeStorage(key, value) {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (err) {
            showError("This browser could not save the draft locally.");
            return false;
        }
    }

    function formatDate(value) {
        if (!value) return "unknown time";
        const date = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString("ko-KR", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
        });
    }

    function collectTemplateForm() {
        return {
            project_name: document.getElementById("tplProjectName").value.trim(),
            client: document.getElementById("tplClient").value.trim(),
            vessel: document.getElementById("tplVessel").value.trim(),
            area: document.getElementById("tplArea").value.trim(),
            software: document.getElementById("tplSoftware").value.trim() || "RadExPro",
            line_count: parseInt(document.getElementById("tplLineCount").value, 10) || 0,
            data_type: selectedDataType,
        };
    }

    function collectUiState() {
        return {
            preset_name: document.getElementById("presetName")?.value.trim() || "",
            selected_preset: document.getElementById("presetSelect")?.value || "",
            revision_author: document.getElementById("revisionAuthor")?.value.trim() || "",
            revision_changes: document.getElementById("revisionChanges")?.value || "",
        };
    }

    function buildSnapshot() {
        return {
            version: 2,
            saved_at: new Date().toISOString(),
            active_tab: document.querySelector("#mainTabs .nav-link.active")?.id || "template-tab",
            selected_data_type: selectedDataType,
            template_form: collectTemplateForm(),
            log_text: document.getElementById("logTextarea").value,
            current_flow: currentFlow,
            ui_state: collectUiState(),
        };
    }

    function updateDraftSafety(snapshot = null, reason = "") {
        const saved = snapshot || readStorage(STORAGE_KEYS.autosave, null);
        const title = document.getElementById("draftSafetyStatus");
        const meta = document.getElementById("draftSafetyMeta");
        const restoreBtn = document.getElementById("draftRestoreBtn");
        const clearBtn = document.getElementById("draftClearBtn");
        if (!title || !meta || !restoreBtn || !clearBtn) return;

        if (!saved) {
            title.textContent = "No autosaved working draft yet.";
            meta.textContent = "This browser will keep your working draft and presets locally.";
            restoreBtn.disabled = true;
            clearBtn.disabled = true;
            return;
        }

        const form = saved.template_form || {};
        const flow = saved.current_flow || {};
        const label = flow.project_name || form.project_name || flow.data_type || form.data_type || "Untitled draft";
        const bits = [`Last saved ${formatDate(saved.saved_at)}`];
        if (Array.isArray(flow.steps)) bits.push(`${flow.steps.length} steps`);
        if (reason) bits.push(reason);
        title.textContent = label;
        meta.textContent = bits.join(" | ");
        restoreBtn.disabled = false;
        clearBtn.disabled = false;
    }

    function saveAutosave(reason = "working draft synced") {
        const snapshot = buildSnapshot();
        if (writeStorage(STORAGE_KEYS.autosave, snapshot)) {
            updateDraftSafety(snapshot, reason);
        }
    }

    function scheduleAutosave(reason = "changes captured") {
        clearTimeout(autosaveTimer);
        autosaveTimer = setTimeout(() => saveAutosave(reason), 250);
    }

    function clearHtmlPreview(message = "Generate or restore a draft to preview the final report layout.") {
        const frame = document.getElementById("htmlPreviewFrame");
        const status = document.getElementById("htmlPreviewStatus");
        if (frame) {
            frame.srcdoc = `<html><body style="font-family:Segoe UI,Arial,sans-serif;padding:32px;color:#475569;background:#f8fafc;">${escapeHtml(message)}</body></html>`;
        }
        if (status) status.textContent = message;
    }

    function ensureMetaFields() {
        const editDesc = document.getElementById("editStepDesc");
        const addDesc = document.getElementById("addStepDesc");
        if (editDesc && !document.getElementById("editStepStage")) {
            editDesc.closest(".mb-3").insertAdjacentHTML("afterend", `
                <div class="mb-3"><label class="form-label">Stage</label><input type="text" class="form-control" id="editStepStage" placeholder="Input &amp; Geometry"></div>
                <div class="mb-3"><label class="form-label">Why This Step</label><textarea class="form-control" id="editStepRationale" rows="2" placeholder="Explain why this step is part of the workflow."></textarea></div>
                <div class="mb-3"><label class="form-label">QC Focus</label><textarea class="form-control" id="editStepQcFocus" rows="2" placeholder="Describe what the reviewer should check here."></textarea></div>
                <div class="mb-3"><label class="form-label">Expected Output</label><textarea class="form-control" id="editStepExpectedOutput" rows="2" placeholder="Describe the expected output or handoff from this step."></textarea></div>
            `);
        }
        if (addDesc && !document.getElementById("addStepStage")) {
            addDesc.closest(".mb-3").insertAdjacentHTML("afterend", `
                <div class="mb-3"><label class="form-label">Stage</label><input type="text" class="form-control" id="addStepStage" placeholder="Signal Conditioning"></div>
                <div class="mb-3"><label class="form-label">Why This Step</label><textarea class="form-control" id="addStepRationale" rows="2" placeholder="Explain why this custom step is needed."></textarea></div>
                <div class="mb-3"><label class="form-label">QC Focus</label><textarea class="form-control" id="addStepQcFocus" rows="2" placeholder="Describe what should be checked after this step."></textarea></div>
                <div class="mb-3"><label class="form-label">Expected Output</label><textarea class="form-control" id="addStepExpectedOutput" rows="2" placeholder="Describe the expected output or handoff from this step."></textarea></div>
            `);
        }
    }

    function renderPresetOptions(selectedName = "") {
        const select = document.getElementById("presetSelect");
        const summary = document.getElementById("presetSummary");
        if (!select || !summary) return;
        const presets = readStorage(STORAGE_KEYS.presets, []);
        const ordered = Array.isArray(presets)
            ? [...presets].sort((a, b) => String(b.saved_at || "").localeCompare(String(a.saved_at || "")))
            : [];
        if (!ordered.length) {
            select.innerHTML = '<option value="">No saved presets yet</option>';
            select.disabled = true;
            summary.textContent = "Presets can store the selected template, project metadata, and the current working flow.";
            return;
        }
        const selectedValue = selectedName || select.value || ordered[0].name;
        select.disabled = false;
        select.innerHTML = ordered.map((preset) => `<option value="${escapeHtml(preset.name)}" ${preset.name === selectedValue ? "selected" : ""}>${escapeHtml(preset.name)} (${escapeHtml(formatDate(preset.saved_at))})</option>`).join("");
        summary.textContent = `${ordered.length} preset(s) saved locally in this browser.`;
    }

    renderTemplateCompare = window.renderTemplateCompare = function (selectedType) {
        const grid = document.getElementById("templateCompareGrid");
        if (!grid) return;
        const ordered = ["SBP", "UHR", "MBES", "MAG", "SSS"];
        grid.innerHTML = ordered.map((dtype) => {
            const info = templateCatalog[dtype];
            if (!info) return "";
            const deliverables = Array.isArray(info.deliverables) ? info.deliverables.slice(0, 2) : [];
            return `<div class="col-md-6 col-xl-4"><div class="template-compare-card ${dtype === selectedType ? "selected" : ""}"><div class="d-flex justify-content-between align-items-start gap-2"><div><div class="compare-type">${escapeHtml(dtype)}</div><div class="compare-label">${escapeHtml(info.label || "")}</div></div><span class="badge bg-secondary">${info.step_count || 0} steps</span></div><div class="compare-focus">${escapeHtml(info.narrative_focus || info.story || "")}</div><div class="compare-software">${escapeHtml(info.default_software || "")}</div><div class="compare-why">${escapeHtml(info.why_template || "")}</div><div class="compare-deliverables">${escapeHtml(deliverables.join(" | ") || "Deliverables defined in the default story.")}</div></div></div>`;
        }).filter(Boolean).join("") || '<div class="text-dim">Template comparison details are unavailable right now.</div>';
    };

    renderGuidedDraft = window.renderGuidedDraft = function (flow) {
        const context = flow?.context || {};
        const readiness = context.readiness || {};
        document.getElementById("storyHeadline").textContent = context.headline || `${flow?.data_type || selectedDataType} workflow story`;
        document.getElementById("storySummary").textContent = context.summary || "Preview how the chosen workflow translates into a report-ready draft story.";
        document.getElementById("storyWhyTemplate").textContent = context.why_template || "The default template rationale will appear here once a flow is loaded.";
        const pill = document.getElementById("readinessPill");
        pill.textContent = readiness.label || "Structured draft in progress";
        pill.className = `readiness-pill tone-${readiness.tone || "info"}`;
        setListItems("deliverablesList", context.deliverables, "Recommended deliverables will appear here once a workflow is loaded.");
        setListItems("openItemsList", context.open_items, "No blocking open items are visible in the current guided draft.");
        const groups = Array.isArray(context.stage_groups) ? context.stage_groups : [];
        document.getElementById("stageSummaryRow").innerHTML = groups.length ? groups.map((group) => `<div class="stage-chip"><span class="chip-title">${escapeHtml(group.stage || "Workflow")}</span><span class="chip-meta">${group.step_count || 0} steps | ${escapeHtml(truncateText(group.summary || "", 90))}</span></div>`).join("") : '<div class="text-dim">Stage summary chips will appear once a workflow is loaded.</div>';
        const sections = Array.isArray(context.report_sections) ? context.report_sections : [];
        document.getElementById("reportPreviewSections").innerHTML = sections.length ? sections.map((section) => `<div class="preview-section"><div class="preview-section-title">${escapeHtml(section.title || "")}</div><div class="preview-section-body">${escapeHtml(section.body || "")}</div></div>`).join("") : '<div class="preview-section"><div class="preview-section-body">The report storyline preview will appear here once a draft is loaded.</div></div>';
    };

    renderSteps = window.renderSteps = function (steps) {
        const container = document.getElementById("stepsContainer");
        container.innerHTML = "";
        if (!steps || !steps.length) {
            container.innerHTML = '<div class="text-dim text-center py-4">No processing steps are defined yet.</div>';
            return;
        }
        steps.forEach((step, idx) => {
            const paramHtml = Object.entries(step.parameters || {}).map(([key, value]) => {
                const isTbd = String(value).toUpperCase().includes("TBD");
                return `<span class="${isTbd ? "param-badge warn" : "param-badge"}">${isTbd ? '<i class="bi bi-exclamation-triangle-fill me-1"></i>' : ""}<strong>${escapeHtml(key)}:</strong> ${escapeHtml(value)}</span>`;
            }).join("");
            const metaCards = [
                step.rationale ? `<div class="step-meta-card"><div class="meta-kicker">Why This Step</div><div class="meta-copy">${escapeHtml(step.rationale)}</div></div>` : "",
                step.qc_focus ? `<div class="step-meta-card"><div class="meta-kicker">QC Focus</div><div class="meta-copy">${escapeHtml(step.qc_focus)}</div></div>` : "",
                step.expected_output ? `<div class="step-meta-card"><div class="meta-kicker">Expected Output</div><div class="meta-copy">${escapeHtml(step.expected_output)}</div></div>` : "",
            ].filter(Boolean).join("");
            container.innerHTML += `<div class="step-card" data-order="${step.order}"><div class="d-flex align-items-start"><span class="step-order">${step.order || idx + 1}</span><div class="flex-grow-1">${step.stage ? `<div class="step-stage-badge">${escapeHtml(step.stage)}</div>` : ""}<span class="step-name">${escapeHtml(step.name || "Untitled step")}</span>${step.description ? `<div class="step-desc">${escapeHtml(step.description)}</div>` : ""}${metaCards ? `<div class="step-meta-grid">${metaCards}</div>` : ""}${paramHtml ? `<div class="d-flex flex-wrap">${paramHtml}</div>` : ""}</div><div class="step-actions"><button class="btn btn-outline-secondary" title="Move up" onclick="moveStep(${step.order}, 'up')" ${idx === 0 ? "disabled" : ""}><i class="bi bi-arrow-up"></i></button><button class="btn btn-outline-secondary" title="Move down" onclick="moveStep(${step.order}, 'down')" ${idx === steps.length - 1 ? "disabled" : ""}><i class="bi bi-arrow-down"></i></button><button class="btn btn-outline-primary" title="Edit" onclick="openEditModal(${step.order})"><i class="bi bi-pencil"></i></button><button class="btn btn-outline-danger" title="Remove" onclick="removeStep(${step.order})"><i class="bi bi-trash"></i></button></div></div></div>`;
        });
    };

    renderPreview = window.renderPreview = function (flow, options = {}) {
        const cloned = JSON.parse(JSON.stringify(flow || {}));
        cloned.steps = Array.isArray(cloned.steps) ? cloned.steps : [];
        currentFlow = cloned;
        lastRenderedFlow = cloned;
        selectedDataType = cloned.data_type || selectedDataType;
        document.querySelectorAll(".data-type-card").forEach((card) => card.classList.toggle("selected", card.dataset.type === selectedDataType));
        document.getElementById("tplProjectName").value = cloned.project_name || "";
        document.getElementById("tplClient").value = cloned.client || "";
        document.getElementById("tplVessel").value = cloned.vessel || "";
        document.getElementById("tplArea").value = cloned.area || "";
        document.getElementById("tplSoftware").value = cloned.software || document.getElementById("tplSoftware").value || "RadExPro";
        document.getElementById("tplLineCount").value = String(cloned.line_count || 0);
        document.getElementById("pvProjectName").textContent = cloned.project_name || "-";
        document.getElementById("pvClient").textContent = cloned.client || "-";
        document.getElementById("pvDataType").textContent = cloned.data_type || "-";
        document.getElementById("pvSoftware").textContent = cloned.software || "-";
        document.getElementById("pvStepCount").textContent = cloned.step_count || cloned.steps.length || "0";
        document.getElementById("pvVessel").textContent = cloned.vessel || "-";
        document.getElementById("pvArea").textContent = cloned.area || "-";
        document.getElementById("pvLineCount").textContent = cloned.line_count || "0";
        renderSteps(cloned.steps);
        renderGuidedDraft(cloned);
        renderTemplateCompare(cloned.data_type || selectedDataType);
        document.getElementById("previewSection").style.display = "block";
        if (!options.preserveScroll) document.getElementById("previewSection").scrollIntoView({ behavior: "smooth", block: "start" });
        loadStatistics(cloned);
        loadValidation(cloned);
        if (!options.skipAutosave) saveAutosave("working draft synced");
        if (!options.skipHtmlRefresh) {
            clearTimeout(htmlPreviewTimer);
            htmlPreviewTimer = setTimeout(() => window.refreshHTMLPreview(false), 400);
        }
    };

    loadStatistics = window.loadStatistics = async function (flow) {
        try {
            const stats = flow?.statistics ? flow.statistics : await fetch("/api/statistics", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(flow),
            }).then((resp) => resp.ok ? resp.json() : null);
            if (!stats) return;
            document.getElementById("statSteps").textContent = stats.step_count || 0;
            document.getElementById("statParams").textContent = stats.total_parameters || 0;
            document.getElementById("statComplete").textContent = `${Math.round(stats.draft_readiness ?? stats.completeness_score ?? 0)}%`;
            document.getElementById("statTBD").textContent = stats.tbd_parameters || 0;
            document.getElementById("statsRow").style.display = "";
        } catch {}
    };

    loadValidation = window.loadValidation = async function (flow) {
        try {
            const result = flow?.validation ? flow.validation : await fetch("/api/validate_params", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(flow),
            }).then((resp) => resp.ok ? resp.json() : null);
            if (!result) return;
            const banner = document.getElementById("validationBanner");
            const warnings = result.warnings || [];
            const errors = result.errors || [];
            if (!errors.length && !warnings.length) {
                banner.className = "validation-banner ok";
                banner.innerHTML = '<i class="bi bi-check-circle-fill"></i> No blocking validation issues were detected in the current draft.';
            } else {
                const messages = [
                    ...errors.slice(0, 3).map((msg) => `<span class="text-danger"><i class="bi bi-x-circle me-1"></i>${escapeHtml(msg)}</span>`),
                    ...warnings.slice(0, 4).map((msg) => `<span><i class="bi bi-exclamation-triangle me-1"></i>${escapeHtml(msg)}</span>`),
                ];
                if ((result.unknown || 0) > 0) messages.push(`<span class="text-dim"><i class="bi bi-info-circle me-1"></i>${result.unknown} parameter(s) are outside the current rule set.</span>`);
                banner.className = "validation-banner warn";
                banner.innerHTML = messages.join("<br>");
            }
            banner.style.display = "";
        } catch {}
    };

    selectDataType = window.selectDataType = function (_el, dtype) {
        const previous = selectedDataType;
        selectedDataType = dtype;
        document.querySelectorAll(".data-type-card").forEach((card) => card.classList.toggle("selected", card.dataset.type === selectedDataType));
        document.getElementById("tplSoftware").value = ({ SBP: "RadExPro", UHR: "RadExPro", MBES: "CARIS HIPS and SIPS", MAG: "Oasis Montaj", SSS: "SonarWiz / CARIS" }[dtype] || "RadExPro");
        renderTemplateCompare(dtype);
        scheduleAutosave("template selection updated");
        if (currentFlow && currentFlow.data_type && currentFlow.data_type !== dtype && previous !== dtype && typeof gvToast === "function") {
            gvToast(`Template selection changed to ${dtype}. Click Preview to regenerate steps; the current draft stays intact until then.`, "info", 3600);
        }
    };

    clearLog = window.clearLog = function () {
        document.getElementById("logTextarea").value = "";
        scheduleAutosave("log text cleared");
        showSuccess("Log text cleared. The working draft remains available until you replace it.");
    };

    function collectParamRows(selector, prefix) {
        const params = {};
        document.querySelectorAll(`${selector} .param-row`).forEach((row) => {
            const key = row.querySelector(`[data-role="${prefix}-key"]`)?.value.trim();
            const value = row.querySelector(`[data-role="${prefix}-val"]`)?.value.trim();
            if (key) params[key] = value || "";
        });
        return params;
    }

    openEditModal = window.openEditModal = function (order) {
        ensureMetaFields();
        if (!currentFlow) return;
        const step = currentFlow.steps.find((item) => item.order === order);
        if (!step) return;
        document.getElementById("editStepOrder").value = order;
        document.getElementById("editStepName").value = step.name || "";
        document.getElementById("editStepDesc").value = step.description || "";
        document.getElementById("editStepStage").value = step.stage || "";
        document.getElementById("editStepRationale").value = step.rationale || "";
        document.getElementById("editStepQcFocus").value = step.qc_focus || "";
        document.getElementById("editStepExpectedOutput").value = step.expected_output || "";
        const editor = document.getElementById("paramEditor");
        editor.innerHTML = "";
        Object.entries(step.parameters || {}).forEach(([key, value]) => {
            editor.innerHTML += createParamRowHTML(key, value, "edit");
        });
        new bootstrap.Modal(document.getElementById("stepEditModal")).show();
    };

    saveStepEdit = window.saveStepEdit = async function () {
        showSpinner("Updating step...");
        try {
            const resp = await fetch("/api/step/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    flow: currentFlow,
                    order: parseInt(document.getElementById("editStepOrder").value, 10),
                    name: document.getElementById("editStepName").value.trim() || undefined,
                    description: document.getElementById("editStepDesc").value.trim(),
                    stage: document.getElementById("editStepStage").value.trim(),
                    rationale: document.getElementById("editStepRationale").value.trim(),
                    qc_focus: document.getElementById("editStepQcFocus").value.trim(),
                    expected_output: document.getElementById("editStepExpectedOutput").value.trim(),
                    parameters: collectParamRows("#paramEditor", "edit"),
                }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || "Step update failed.");
            bootstrap.Modal.getInstance(document.getElementById("stepEditModal"))?.hide();
            renderPreview(data, { preserveScroll: true });
            showSuccess("Step updated.");
        } catch (err) {
            showError(err.message || "Step update failed.");
        } finally {
            hideSpinner();
        }
    };

    openAddStepModal = window.openAddStepModal = function () {
        ensureMetaFields();
        if (!currentFlow) {
            showError("Create or restore a draft before adding custom steps.");
            return;
        }
        document.getElementById("addStepName").value = "";
        document.getElementById("addStepDesc").value = "";
        document.getElementById("addStepStage").value = "";
        document.getElementById("addStepRationale").value = "";
        document.getElementById("addStepQcFocus").value = "";
        document.getElementById("addStepExpectedOutput").value = "";
        document.getElementById("newParamEditor").innerHTML = "";
        const select = document.getElementById("addStepPosition");
        select.innerHTML = '<option value="">Append to the end</option>';
        (currentFlow.steps || []).forEach((step) => {
            select.innerHTML += `<option value="${step.order}">After Step ${step.order} (${escapeHtml(step.name)})</option>`;
        });
        new bootstrap.Modal(document.getElementById("addStepModal")).show();
    };

    saveNewStep = window.saveNewStep = async function () {
        const name = document.getElementById("addStepName").value.trim();
        if (!name) {
            showError("Step name is required.");
            return;
        }
        showSpinner("Adding step...");
        try {
            const resp = await fetch("/api/step/add", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    flow: currentFlow,
                    name,
                    description: document.getElementById("addStepDesc").value.trim(),
                    stage: document.getElementById("addStepStage").value.trim(),
                    rationale: document.getElementById("addStepRationale").value.trim(),
                    qc_focus: document.getElementById("addStepQcFocus").value.trim(),
                    expected_output: document.getElementById("addStepExpectedOutput").value.trim(),
                    parameters: collectParamRows("#newParamEditor", "new"),
                    position: document.getElementById("addStepPosition").value ? parseInt(document.getElementById("addStepPosition").value, 10) + 1 : null,
                }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || "Step add failed.");
            bootstrap.Modal.getInstance(document.getElementById("addStepModal"))?.hide();
            renderPreview(data, { preserveScroll: true });
            showSuccess(`"${name}" added to the workflow.`);
        } catch (err) {
            showError(err.message || "Step add failed.");
        } finally {
            hideSpinner();
        }
    };

    exportHTML = window.exportHTML = async function () {
        if (!currentFlow) {
            showError("Generate or restore a draft first.");
            return;
        }
        showSpinner("Opening HTML preview...");
        try {
            const resp = await fetch("/api/export_html", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(currentFlow),
            });
            if (!resp.ok) {
                const errorBody = await resp.json();
                throw new Error(errorBody.error || "HTML preview failed.");
            }
            const html = await resp.text();
            const win = window.open("", "_blank");
            if (!win) throw new Error("Popup blocked. Allow popups to open the HTML preview window.");
            win.document.write(html);
            win.document.close();
            showSuccess("HTML preview opened in a new window.");
        } catch (err) {
            showError(err.message || "HTML preview failed.");
        } finally {
            hideSpinner();
        }
    };

    window.refreshHTMLPreview = async function (manual = true) {
        if (!currentFlow) {
            clearHtmlPreview();
            return;
        }
        const status = document.getElementById("htmlPreviewStatus");
        if (status) status.textContent = manual ? "Refreshing live report preview..." : "Syncing live report preview...";
        try {
            const resp = await fetch("/api/export_html", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(currentFlow),
            });
            if (!resp.ok) {
                const errorBody = await resp.json();
                throw new Error(errorBody.error || "Live HTML preview failed.");
            }
            document.getElementById("htmlPreviewFrame").srcdoc = await resp.text();
            if (status) status.textContent = `Live preview synced ${formatDate(new Date())}`;
        } catch (err) {
            if (status) status.textContent = err.message || "Live HTML preview is unavailable.";
        }
    };

    function clonePayload(value) {
        if (value === null || value === undefined) return value;
        return JSON.parse(JSON.stringify(value));
    }

    function defaultSoftwareFor(dtype) {
        return ({
            SBP: "RadExPro",
            UHR: "RadExPro",
            MBES: "CARIS HIPS and SIPS",
            MAG: "Oasis Montaj",
            SSS: "SonarWiz / CARIS",
        }[dtype] || "RadExPro");
    }

    function syncCurrentFlowFromForm() {
        if (!currentFlow) return;
        const form = collectTemplateForm();
        currentFlow.project_name = form.project_name;
        currentFlow.client = form.client;
        currentFlow.vessel = form.vessel;
        currentFlow.area = form.area;
        currentFlow.line_count = form.line_count;

        const selectedDefaultSoftware = defaultSoftwareFor(selectedDataType);
        if (
            !currentFlow.software
            || selectedDataType === currentFlow.data_type
            || form.software !== selectedDefaultSoftware
        ) {
            currentFlow.software = form.software;
        }

        lastRenderedFlow = clonePayload(currentFlow);
    }

    function renderPresetSummary(selectedName = "") {
        const summary = document.getElementById("presetSummary");
        if (!summary) return;
        const presets = readStorage(STORAGE_KEYS.presets, []);
        const selected = Array.isArray(presets)
            ? presets.find((preset) => preset.name === (selectedName || document.getElementById("presetSelect")?.value))
            : null;
        if (!selected) {
            if (!Array.isArray(presets) || !presets.length) {
                summary.textContent = "Presets can store the selected template, project metadata, and the current working flow.";
            } else {
                summary.textContent = `${presets.length} preset(s) saved locally in this browser.`;
            }
            return;
        }

        const flow = selected.snapshot?.current_flow || {};
        const parts = [
            flow.project_name || flow.data_type || selected.name,
            flow.data_type || selected.snapshot?.selected_data_type || "Template",
        ];
        if (Array.isArray(flow.steps)) parts.push(`${flow.steps.length} steps`);
        parts.push(`saved ${formatDate(selected.saved_at)}`);
        summary.textContent = parts.join(" | ");
    }

    function setActiveTab(tabId) {
        if (!tabId || !window.bootstrap?.Tab) return;
        const button = document.getElementById(tabId);
        if (button) {
            bootstrap.Tab.getOrCreateInstance(button).show();
        }
    }

    function applySnapshot(snapshot, options = {}) {
        if (!snapshot || typeof snapshot !== "object") return false;

        const flow = clonePayload(snapshot.current_flow || snapshot.flow || (Array.isArray(snapshot.steps) ? snapshot : null));
        const form = snapshot.template_form || {};
        const source = flow || {};
        const targetType = snapshot.selected_data_type || source.data_type || form.data_type || selectedDataType || "SBP";

        selectedDataType = targetType;
        document.querySelectorAll(".data-type-card").forEach((card) => {
            card.classList.toggle("selected", card.dataset.type === selectedDataType);
        });

        document.getElementById("tplProjectName").value = source.project_name || form.project_name || "";
        document.getElementById("tplClient").value = source.client || form.client || "";
        document.getElementById("tplVessel").value = source.vessel || form.vessel || "";
        document.getElementById("tplArea").value = source.area || form.area || "";
        document.getElementById("tplSoftware").value = source.software || form.software || defaultSoftwareFor(targetType);
        document.getElementById("tplLineCount").value = String(source.line_count || form.line_count || 0);
        document.getElementById("logTextarea").value = snapshot.log_text || "";

        if (snapshot.ui_state) {
            if (document.getElementById("presetName")) document.getElementById("presetName").value = snapshot.ui_state.preset_name || "";
            if (document.getElementById("revisionAuthor")) document.getElementById("revisionAuthor").value = snapshot.ui_state.revision_author || "";
            if (document.getElementById("revisionChanges")) document.getElementById("revisionChanges").value = snapshot.ui_state.revision_changes || "";
        }

        renderTemplateCompare(selectedDataType);

        if (flow && Array.isArray(flow.steps)) {
            renderPreview(flow, { preserveScroll: true, skipAutosave: true });
        } else {
            currentFlow = null;
            lastRenderedFlow = null;
            document.getElementById("previewSection").style.display = "none";
            document.getElementById("statsRow").style.display = "none";
            document.getElementById("validationBanner").style.display = "none";
            clearHtmlPreview();
        }

        if (!options.skipAutosave) saveAutosave(options.reason || "working draft restored");
        updateDraftSafety(readStorage(STORAGE_KEYS.autosave, snapshot), options.reason || "");
        renderPresetOptions(options.selectedPreset || snapshot.ui_state?.selected_preset || "");
        renderPresetSummary(options.selectedPreset || snapshot.ui_state?.selected_preset || "");
        setActiveTab(snapshot.active_tab || "template-tab");
        if (options.message) showSuccess(options.message);
        return true;
    }

    function normalizeImportedSnapshot(payload, filename = "") {
        if (!payload || typeof payload !== "object") return null;
        if (payload.current_flow || payload.template_form) return payload;
        if (payload.flow && typeof payload.flow === "object") {
            return {
                selected_data_type: payload.flow.data_type || selectedDataType,
                template_form: payload.flow,
                current_flow: payload.flow,
                ui_state: { preset_name: filename },
            };
        }
        if (Array.isArray(payload.steps)) {
            return {
                selected_data_type: payload.data_type || selectedDataType,
                template_form: payload,
                current_flow: payload,
                ui_state: { preset_name: filename },
            };
        }
        return null;
    }

    async function fetchRevisionFlow(version) {
        const resp = await fetch(`/api/revision/${version}`);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || `Could not load revision v${version}.`);
        return data;
    }

    async function loadRevisionHistory(selectedVersion = "") {
        const select = document.getElementById("revisionSelect");
        const note = document.getElementById("revisionHistoryNote");
        if (!select || !note) return;
        try {
            const resp = await fetch("/api/revision/history");
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || "Could not load revision history.");
            revisionCatalog = Array.isArray(data.revisions) ? [...data.revisions].reverse() : [];
            if (!revisionCatalog.length) {
                select.innerHTML = '<option value="">No revisions yet</option>';
                select.disabled = true;
                note.textContent = "Save a revision to compare the current draft against earlier checkpoints.";
                return;
            }

            const activeValue = String(selectedVersion || select.value || revisionCatalog[0].version);
            select.disabled = false;
            select.innerHTML = revisionCatalog.map((revision) => {
                const label = [`v${revision.version}`, revision.author || "Unknown author", formatDate(revision.timestamp)].join(" | ");
                return `<option value="${revision.version}" ${String(revision.version) === activeValue ? "selected" : ""}>${escapeHtml(label)}</option>`;
            }).join("");

            const current = revisionCatalog.find((revision) => String(revision.version) === activeValue) || revisionCatalog[0];
            note.textContent = current?.changes
                ? `Selected revision note: ${current.changes}`
                : `${revisionCatalog.length} revision checkpoint(s) are available for comparison.`;
        } catch (err) {
            select.innerHTML = '<option value="">Revision history unavailable</option>';
            select.disabled = true;
            note.textContent = err.message || "Revision history is unavailable right now.";
        }
    }

    function describeModifiedFields(change) {
        const oldInfo = change.old || {};
        const newInfo = change.new || {};
        const fields = [];
        if ((oldInfo.description || "") !== (newInfo.description || "")) fields.push("description");
        if ((oldInfo.stage || "") !== (newInfo.stage || "")) fields.push("stage");
        if ((oldInfo.rationale || "") !== (newInfo.rationale || "")) fields.push("step rationale");
        if ((oldInfo.qc_focus || "") !== (newInfo.qc_focus || "")) fields.push("QC focus");
        if ((oldInfo.expected_output || "") !== (newInfo.expected_output || "")) fields.push("expected output");
        if (JSON.stringify(oldInfo.parameters || {}) !== JSON.stringify(newInfo.parameters || {})) fields.push("parameters");
        return fields.length ? fields.join(", ") : "step details";
    }

    function renderRevisionDiff(diff, versionLabel) {
        const container = document.getElementById("revisionDiffOutput");
        if (!container) return;

        const metadataChanges = Object.entries(diff.metadata_changes || {});
        const addedSteps = diff.added_steps || [];
        const removedSteps = diff.removed_steps || [];
        const modifiedSteps = diff.modified_steps || [];

        if (!metadataChanges.length && !addedSteps.length && !removedSteps.length && !modifiedSteps.length) {
            container.innerHTML = `<div class="inline-status">No differences were found between the current draft and ${escapeHtml(versionLabel)}.</div>`;
            return;
        }

        const metadataLabels = {
            project_name: "Project name",
            client: "Client",
            data_type: "Data type",
            vessel: "Vessel",
            area: "Survey area",
            date: "Date",
            software: "Software",
            software_version: "Software version",
            line_count: "Line count",
            notes: "Notes",
        };

        const sections = [];
        if (metadataChanges.length) {
            sections.push(`<ul class="diff-list">${metadataChanges.map(([field, values]) => `<li><strong>${escapeHtml(metadataLabels[field] || field)}</strong>: ${escapeHtml(values.old || "-")} -> ${escapeHtml(values.new || "-")}</li>`).join("")}</ul>`);
        }
        if (addedSteps.length) {
            sections.push(`<ul class="diff-list">${addedSteps.map((step) => `<li><strong>Added:</strong> ${escapeHtml(step.name)}${step.stage ? ` (${escapeHtml(step.stage)})` : ""}</li>`).join("")}</ul>`);
        }
        if (removedSteps.length) {
            sections.push(`<ul class="diff-list">${removedSteps.map((step) => `<li><strong>Removed:</strong> ${escapeHtml(step.name)}${step.stage ? ` (${escapeHtml(step.stage)})` : ""}</li>`).join("")}</ul>`);
        }
        if (modifiedSteps.length) {
            sections.push(`<ul class="diff-list">${modifiedSteps.map((change) => `<li><strong>${escapeHtml(change.name)}</strong>: ${escapeHtml(describeModifiedFields(change))}</li>`).join("")}</ul>`);
        }

        container.innerHTML = `
            <div class="diff-summary-bar">
                <span class="diff-pill">Metadata ${metadataChanges.length}</span>
                <span class="diff-pill">Added ${addedSteps.length}</span>
                <span class="diff-pill">Removed ${removedSteps.length}</span>
                <span class="diff-pill">Modified ${modifiedSteps.length}</span>
            </div>
            ${sections.join("")}
        `;
    }

    window.saveCurrentPreset = function () {
        const nameInput = document.getElementById("presetName");
        const select = document.getElementById("presetSelect");
        const fallbackName = `${currentFlow?.project_name || selectedDataType || "Draft"} ${new Date().toLocaleDateString("ko-KR")}`;
        const name = (nameInput?.value || "").trim() || fallbackName;
        const snapshot = buildSnapshot();
        const presets = readStorage(STORAGE_KEYS.presets, []).filter((preset) => preset.name !== name);
        presets.push({
            name,
            saved_at: new Date().toISOString(),
            snapshot: clonePayload(snapshot),
        });
        if (!writeStorage(STORAGE_KEYS.presets, presets)) return;
        if (nameInput) nameInput.value = name;
        if (select) select.value = name;
        renderPresetOptions(name);
        renderPresetSummary(name);
        showSuccess(`Preset "${name}" saved in this browser.`);
    };

    window.loadSelectedPreset = function () {
        const name = document.getElementById("presetSelect")?.value;
        const presets = readStorage(STORAGE_KEYS.presets, []);
        const selected = Array.isArray(presets) ? presets.find((preset) => preset.name === name) : null;
        if (!selected) {
            showError("Select a saved preset first.");
            return;
        }
        applySnapshot(selected.snapshot, {
            selectedPreset: selected.name,
            reason: "preset restored",
            message: `Preset "${selected.name}" restored.`,
        });
    };

    window.deleteSelectedPreset = function () {
        const name = document.getElementById("presetSelect")?.value;
        if (!name) {
            showError("Select a preset to delete.");
            return;
        }
        const remaining = readStorage(STORAGE_KEYS.presets, []).filter((preset) => preset.name !== name);
        if (!writeStorage(STORAGE_KEYS.presets, remaining)) return;
        renderPresetOptions();
        renderPresetSummary();
        showSuccess(`Preset "${name}" deleted from this browser.`);
    };

    window.restoreAutosavedDraft = function () {
        const snapshot = readStorage(STORAGE_KEYS.autosave, null);
        if (!snapshot) {
            showError("There is no autosaved draft to restore.");
            return;
        }
        applySnapshot(snapshot, {
            reason: "autosaved draft restored",
            message: "Autosaved draft restored.",
        });
    };

    window.clearAutosavedDraft = function () {
        window.localStorage.removeItem(STORAGE_KEYS.autosave);
        updateDraftSafety(null);
        showSuccess("Autosaved browser draft cleared. The current on-screen draft is still available.");
    };

    window.importJSONFile = async function (event) {
        const file = event?.target?.files?.[0];
        if (!file) return;
        try {
            const payload = JSON.parse(await file.text());
            const snapshot = normalizeImportedSnapshot(payload, file.name.replace(/\.json$/i, ""));
            if (!snapshot) throw new Error("The selected JSON file does not match a supported draft format.");
            applySnapshot(snapshot, {
                reason: "json import restored",
                message: `Imported draft from ${file.name}.`,
            });
        } catch (err) {
            showError(err.message || "JSON import failed.");
        } finally {
            event.target.value = "";
        }
    };

    window.saveRevision = async function () {
        if (!currentFlow) {
            showError("Generate or restore a draft before saving a revision.");
            return;
        }
        syncCurrentFlowFromForm();
        showSpinner("Saving revision...");
        try {
            const resp = await fetch("/api/revision/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    flow: currentFlow,
                    author: document.getElementById("revisionAuthor")?.value.trim() || "",
                    changes: document.getElementById("revisionChanges")?.value.trim() || "",
                }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || "Revision save failed.");
            await loadRevisionHistory(String(data.version));
            showSuccess(`Revision v${data.version} saved.`);
        } catch (err) {
            showError(err.message || "Revision save failed.");
        } finally {
            hideSpinner();
        }
    };

    window.compareWithSelectedRevision = async function () {
        const version = document.getElementById("revisionSelect")?.value;
        if (!currentFlow) {
            showError("Generate or restore a draft before comparing revisions.");
            return;
        }
        if (!version) {
            showError("Select a revision to compare.");
            return;
        }

        syncCurrentFlowFromForm();
        showSpinner("Comparing revisions...");
        try {
            const revisionFlow = await fetchRevisionFlow(version);
            const resp = await fetch("/api/compare_flows", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ flow1: revisionFlow, flow2: currentFlow }),
            });
            const diff = await resp.json();
            if (!resp.ok) throw new Error(diff.error || "Revision comparison failed.");
            renderRevisionDiff(diff, `revision v${version}`);
            document.getElementById("revisionHistoryNote").textContent = `Current draft compared against revision v${version}.`;
        } catch (err) {
            showError(err.message || "Revision comparison failed.");
        } finally {
            hideSpinner();
        }
    };

    window.restoreSelectedRevision = async function () {
        const version = document.getElementById("revisionSelect")?.value;
        if (!version) {
            showError("Select a revision to restore.");
            return;
        }
        showSpinner("Restoring revision...");
        try {
            const revisionFlow = await fetchRevisionFlow(version);
            applySnapshot({
                selected_data_type: revisionFlow.data_type,
                template_form: revisionFlow,
                current_flow: revisionFlow,
                active_tab: "author-tab",
            }, {
                reason: `revision v${version} restored`,
                message: `Revision v${version} restored into the editor.`,
            });
        } catch (err) {
            showError(err.message || "Revision restore failed.");
        } finally {
            hideSpinner();
        }
    };

    const originalRefreshHTMLPreview = window.refreshHTMLPreview;
    window.refreshHTMLPreview = async function (manual = true) {
        syncCurrentFlowFromForm();
        return originalRefreshHTMLPreview(manual);
    };

    const originalExportHTML = window.exportHTML;
    window.exportHTML = async function () {
        syncCurrentFlowFromForm();
        return originalExportHTML();
    };

    ["downloadWordReport", "downloadExcelReport", "downloadTextReport", "exportJSON"].forEach((name) => {
        const original = window[name];
        if (typeof original === "function") {
            window[name] = async function (...args) {
                syncCurrentFlowFromForm();
                return original.apply(this, args);
            };
        }
    });

    const metadataInputs = [
        "tplProjectName",
        "tplClient",
        "tplVessel",
        "tplArea",
        "tplSoftware",
        "tplLineCount",
        "revisionAuthor",
        "revisionChanges",
        "presetName",
    ];
    metadataInputs.forEach((id) => {
        const element = document.getElementById(id);
        if (!element) return;
        element.addEventListener("input", () => {
            syncCurrentFlowFromForm();
            scheduleAutosave("metadata updated");
            clearTimeout(htmlPreviewTimer);
            htmlPreviewTimer = setTimeout(() => window.refreshHTMLPreview(false), 650);
        });
    });

    const logTextarea = document.getElementById("logTextarea");
    if (logTextarea) {
        logTextarea.addEventListener("input", () => scheduleAutosave("log text updated"));
    }

    const presetSelect = document.getElementById("presetSelect");
    if (presetSelect) {
        presetSelect.addEventListener("change", () => renderPresetSummary(presetSelect.value));
    }

    const revisionSelect = document.getElementById("revisionSelect");
    if (revisionSelect) {
        revisionSelect.addEventListener("change", () => loadRevisionHistory(revisionSelect.value));
    }

    const jsonImportInput = document.getElementById("jsonImportInput");
    if (jsonImportInput) {
        jsonImportInput.addEventListener("change", window.importJSONFile);
    }

    document.querySelectorAll("#mainTabs button").forEach((button) => {
        button.addEventListener("shown.bs.tab", () => {
            if (!lastRenderedFlow) return;
            currentFlow = clonePayload(lastRenderedFlow);
            document.getElementById("previewSection").style.display = "block";
            renderSteps(currentFlow.steps || []);
            renderGuidedDraft(currentFlow);
            loadStatistics(currentFlow);
            loadValidation(currentFlow);
        });
    });

    window.addEventListener("beforeunload", () => {
        if (currentFlow || document.getElementById("logTextarea")?.value.trim()) {
            syncCurrentFlowFromForm();
            saveAutosave("browser session closed");
        }
    });

    ensureMetaFields();
    updateDraftSafety();
    renderPresetOptions();
    renderPresetSummary();
    clearHtmlPreview();
    loadRevisionHistory();
    if (!Object.keys(templateCatalog || {}).length && typeof window.loadDataTypeCatalog === "function") {
        window.loadDataTypeCatalog();
    } else {
        renderTemplateCompare(selectedDataType);
    }

    const autosavedDraft = readStorage(STORAGE_KEYS.autosave, null);
    if (autosavedDraft && !currentFlow) {
        applySnapshot(autosavedDraft, {
            reason: "autosaved draft loaded on startup",
            message: "Autosaved draft loaded from this browser.",
        });
    }
})();
