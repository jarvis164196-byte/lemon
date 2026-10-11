const $ = (s) => document.querySelector(s);
const escape = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let visionAvailable = false;
let project = null,
  selected = null,
  pinned = null,
  plan = null,
  mode = "reference",
  busy = false;
const requests = new Map();
function activity(message) {
  $("#activity").textContent = message;
}
function notice(message = "") {
  $("#notice").textContent = message;
  $("#notice").hidden = !message;
}
async function api(path, body, method = "POST") {
  const options =
    body === undefined
      ? {}
      : {
          method,
          headers:
            body instanceof FormData
              ? {}
              : { "Content-Type": "application/json" },
          body: body instanceof FormData ? body : JSON.stringify(body),
        };
  const response = await fetch("/api" + path, options);
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Please check the requested values.",
    );
  return data;
}
async function task(message, action) {
  if (busy) return;
  busy = true;
  document.body.classList.add("busy");
  notice();
  activity(message);
  lockControls();
  try {
    await action();
  } catch (error) {
    notice(error.message);
    activity("Action stopped. Review the message above.");
  } finally {
    busy = false;
    document.body.classList.remove("busy");
    lockControls();
  }
}
function lockControls() {
  document
    .querySelectorAll(
      "button:not([data-node]):not([data-view]), #import-form input, #strength, #planner, #instruction, #vision-consent",
    )
    .forEach((b) => (b.disabled = busy));
  if (project && !busy) {
    $("#vision-consent").disabled = !visionAvailable;
    $("#propose").disabled = project.session_status !== "ready";
    const node = project.nodes[selected];
    $("#restore").disabled = !node?.healthy;
    $("#export").disabled = !node?.healthy;
    document
      .querySelectorAll("[data-run]")
      .forEach((b) => (b.disabled = project.session_status !== "ready"));
  }
}
const asset = (role, id) =>
  `/api/projects/${project.id}/assets/${role}${id ? "?asset_id=" + encodeURIComponent(id) : ""}`;
const nodeLabel = (id) => project.nodes[id]?.display_id || "None";
function photo(url, title, subtitle, alt) {
  return `<figure class="photo-frame"><img src="${url}" alt="${escape(alt)}"><figcaption><strong>${escape(title)}</strong><span>${escape(subtitle)}</span></figcaption></figure>`;
}
function render() {
  $("#welcome").hidden = true;
  $("#workbench").hidden = false;
  $("#study-name").textContent = project.name;
  $("#version-count").textContent = Object.keys(project.nodes).length;
  const nodes = Object.values(project.nodes);
  const ordered = [];
  function visit(parent, depth) {
    nodes
      .filter((n) => n.parent_id === parent)
      .forEach((n) => {
        ordered.push([n, depth]);
        visit(n.id, depth + 1);
      });
  }
  visit(null, 0);
  $("#history-list").innerHTML = ordered
    .map(([n, depth]) => {
      const tips = Object.values(project.branches)
        .filter((b) => b.tip_node_id === n.id)
        .map((b) => b.name);
      return `<div class="node-wrap depth-${Math.min(depth, 4)}">${tips.length ? `<div class="branch-label">${escape(tips.join(" · "))} / tip</div>` : ""}<button class="history-node ${n.id === selected ? "selected" : ""}" data-node="${n.id}" aria-pressed="${n.id === selected}"><img src="${asset("preview", n.id)}" alt=""><span><span class="node-id">${n.parent_id ? "↳ " : ""}${n.display_id}</span>${n.id === project.working_node_id ? '<span class="badge">WORKING</span>' : ""}<span class="node-label">${escape(n.label)}</span>${!n.healthy ? '<span class="badge">UNAVAILABLE</span>' : ""}</span></button></div>`;
    })
    .join("");
  $("#storage").textContent =
    `${(project.storage_bytes / 1024 ** 2).toFixed(1)} MB · All versions preserved`;
  renderPreview();
  renderPlan();
  $("#vision-consent").checked = Boolean(project.vision_consent?.granted);
  $("#cloud-state").textContent = visionAvailable
    ? `OpenAI: ${project.vision_consent?.granted ? "permission granted for this project" : "permission required"}`
    : "Cloud AI: not configured";
  const n = project.nodes[selected];
  $("#node-details").textContent = JSON.stringify(
    {
      version: n.display_id,
      parent: n.parent_id ? nodeLabel(n.parent_id) : null,
      operation: n.step,
      checkpoint_sha256: n.checkpoint_hash,
      gimp: n.evidence.environment?.version,
      verified: n.healthy,
    },
    null,
    2,
  );
  $("#restore").textContent = `Restore ${n.display_id} and continue`;
  $("#export").textContent = `Export ${n.display_id} ↗`;
  $("#plan-base").textContent =
    `Edits start from ${nodeLabel(project.working_node_id)} · Working version`;
  if (project.session_status === "recovery_required")
    notice(
      "The last operation did not commit. Restore a healthy saved version to continue. Previous versions are preserved.",
    );
  lockControls();
}
function renderPreview() {
  const n = project.nodes[selected];
  let content = "";
  if (mode === "compare")
    content += photo(
      asset("preview", pinned),
      `${nodeLabel(pinned)} / Before`,
      project.nodes[pinned].label,
      "Pinned comparison version",
    );
  content += photo(
    asset("preview", selected),
    `${n.display_id} / ${mode === "compare" ? "After" : "Your photo"}`,
    n.label,
    `${n.display_id}: ${n.label}`,
  );
  if (mode === "reference")
    content += photo(
      asset("reference"),
      "Reference / Inspiration",
      "Read-only original",
      "Reference photo",
    );
  $("#preview-grid").innerHTML = content;
  $("#preview-grid").classList.toggle("single", mode === "single");
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === mode));
  $("#viewing-label").textContent =
    `Viewing ${n.display_id}${n.id === project.working_node_id ? "" : " · Read-only preview"}`;
  $("#working-label").textContent =
    `Working version ${nodeLabel(project.working_node_id)}`;
}
function curve(values) {
  return `<svg class="curve" viewBox="0 0 256 70" role="img" aria-label="Proposed tone curve"><path class="baseline" d="M0 70 L256 0"/><polyline class="line" points="${values.map((y, x) => `${x},${70 - y * 70}`).join(" ")}"/></svg>`;
}
function renderPlan() {
  if (!plan) {
    $("#plan-steps").innerHTML = "";
    $("#plan-actions").innerHTML = "";
    return;
  }
  const stale =
    plan.expected_base !== project.working_node_id ||
    plan.expected_revision !== project.revision;
  $("#plan-steps").innerHTML = plan.steps
    .map(
      (s, i) =>
        `<div class="step ${i < plan.next_step ? "done" : ""}"><div class="step-heading"><span class="step-number">${i < plan.next_step ? "✓" : i + 1}</span>${escape(s.label)}</div><p>${escape(s.explanation)}</p>${s.tool === "curves" ? curve(s.arguments.values) : ""}<details><summary>Exact native parameters</summary><pre>${escape(JSON.stringify({ tool: s.tool, ...s.arguments }, null, 2))}</pre></details></div>`,
    )
    .join("");
  if (stale)
    $("#plan-actions").innerHTML =
      '<p class="small muted">The working version changed. Analyze again to create a new plan.</p>';
  else if (plan.next_step < plan.steps.length)
    $("#plan-actions").innerHTML =
      `<button class="primary full" data-run="one">Approve step ${plan.next_step + 1} on ${nodeLabel(project.working_node_id)}</button>${plan.next_step < 2 ? '<button class="quiet full" data-run="all">Approve remaining steps</button>' : ""}`;
  else
    $("#plan-actions").innerHTML =
      '<p class="small muted">✓ Recipe complete. Compare the result and keep what you like.</p>';
}
async function refresh() {
  project = await api(`/projects/${project.id}`);
  if (plan) plan = project.plans[plan.id];
}
async function openProject(id) {
  project = await api(`/projects/${id}`);
  if (!project.working_node_id)
    throw new Error(
      "This import has no verified root checkpoint. Create a new project; the failed import remains available on disk.",
    );
  selected = project.working_node_id;
  pinned = Object.values(project.nodes).find((n) => !n.parent_id).id;
  plan = null;
  $("#planner").value = "local";
  localStorage.setItem("lemon-project", id);
  render();
  activity("Project opened. Select any version to compare.");
}
async function recent() {
  const projects = await api("/projects");
  $("#recent-projects").innerHTML = projects.length
    ? projects
        .map(
          (p) =>
            `<button data-project="${p.id}">${escape(p.name)}<small>${p.versions} versions</small></button>`,
        )
        .join("")
    : '<p class="small muted">Your color studies will appear here.</p>';
}
for (const role of ["source", "reference"]) {
  let oldURL;
  $(`#${role}-file`).addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (oldURL) URL.revokeObjectURL(oldURL);
    oldURL = URL.createObjectURL(file);
    const img = $(`#${role}-upload-preview`);
    img.src = oldURL;
    img.hidden = false;
    $(`#${role}-filename`).textContent = file.name;
  });
}
$("#import-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const data = new FormData(e.target);
  task(
    "Creating your original checkpoint in GIMP. Saving and reopening for verification…",
    async () => {
      project = await api("/projects", data);
      await openProject(project.id);
      activity(
        "Original saved and verified. Your reference is ready to analyze.",
      );
    },
  );
});
$("#vision-consent").addEventListener("change", (e) => {
  const granted = e.target.checked;
  task(
    granted ? "Recording project permission…" : "Revoking project permission…",
    async () => {
      const record = await api(`/projects/${project.id}/consent`, { granted });
      project.vision_consent = record;
      render();
      activity(
        granted
          ? "Permission recorded for this project. Analyze with OpenAI only when you choose it."
          : "OpenAI permission revoked. Local analysis remains available.",
      );
    },
  );
});
$("#strength").addEventListener(
  "input",
  (e) => ($("#strength-value").textContent = e.target.value + "%"),
);
$("#propose").addEventListener("click", () =>
  task(
    $("#planner").value === "openai"
      ? "Preparing approved previews and asking OpenAI for a bounded recipe…"
      : "Analyzing local tone and color…",
    async () => {
      plan = await api(`/projects/${project.id}/plans`, {
        strength: Number($("#strength").value) / 100,
        planner: $("#planner").value,
        instruction: $("#instruction").value,
      });
      render();
      activity(
        "Three native adjustments proposed. Review the recipe before approving.",
      );
    },
  ),
);
async function confirmAction(title, message, label) {
  const dialog = $("#confirm-dialog");
  $("#confirm-title").textContent = title;
  $("#confirm-message").textContent = message;
  $("#confirm-action").textContent = label;
  dialog.returnValue = "";
  return new Promise((resolve) => {
    dialog.addEventListener(
      "close",
      () => resolve(dialog.returnValue === "approve"),
      { once: true },
    );
    dialog.showModal();
  });
}
$("#restore").addEventListener("click", async () => {
  const nodeId = selected;
  if (
    !(await confirmAction(
      `Restore ${nodeLabel(nodeId)}?`,
      "This becomes your working version. Every saved version remains available. The next edit may create a new branch.",
      "Restore version",
    ))
  )
    return;
  task("Reopening and verifying the selected checkpoint…", async () => {
    project = await api(`/projects/${project.id}/restore`, { node_id: nodeId });
    plan = null;
    render();
    activity(`Restored ${nodeLabel(nodeId)}. Earlier branches are preserved.`);
  });
});
$("#pin").addEventListener("click", () => {
  pinned = selected;
  mode = "compare";
  renderPreview();
  activity(
    `${nodeLabel(pinned)} pinned as Before. Select another version to compare.`,
  );
});
$("#export").addEventListener("click", async () => {
  const nodeId = selected;
  if (
    !(await confirmAction(
      `Export ${nodeLabel(nodeId)}?`,
      "GIMP will export this saved version at full resolution as a PNG. The working version is unchanged.",
      "Export PNG",
    ))
  )
    return;
  task(
    `Exporting ${nodeLabel(nodeId)} from its saved GIMP checkpoint…`,
    async () => {
      const data = await api(`/projects/${project.id}/exports`, {
        node_id: nodeId,
      });
      const a = document.createElement("a");
      a.href = asset("export", data.export_id);
      a.download = `lemon-${nodeLabel(nodeId)}.png`;
      a.click();
      activity(
        `Exported ${nodeLabel(nodeId)} at full resolution. Provenance saved with the export.`,
      );
    },
  );
});
$("#new-project").addEventListener("click", () =>
  task("Ready for a new color study.", async () => {
    $("#workbench").hidden = true;
    $("#welcome").hidden = false;
    await recent();
  }),
);
document.addEventListener("click", (e) => {
  const node = e.target.closest("[data-node]");
  if (node) {
    selected = node.dataset.node;
    render();
    return;
  }
  const view = e.target.closest("[data-view]");
  if (view) {
    mode = view.dataset.view;
    renderPreview();
    return;
  }
  const projectButton = e.target.closest("[data-project]");
  if (projectButton) {
    task("Opening your saved color study…", () =>
      openProject(projectButton.dataset.project),
    );
    return;
  }
  const run = e.target.closest("[data-run]");
  if (run)
    task("Applying the approved recipe in GIMP…", async () => {
      const count =
        run.dataset.run === "all" ? plan.steps.length - plan.next_step : 1;
      for (let i = 0; i < count; i++) {
        const step = plan.next_step,
          key = plan.id + ":" + step;
        if (!requests.has(key))
          requests.set(key, crypto.randomUUID().replaceAll("-", ""));
        activity(
          `Step ${step + 1}: ${plan.steps[step].label}. Editing, saving, and reopening…`,
        );
        let result;
        try {
          result = await api(`/projects/${project.id}/run`, {
            plan_id: plan.id,
            plan_hash: plan.hash,
            step_index: step,
            request_id: requests.get(key),
          });
        } catch (error) {
          await refresh();
          render();
          throw error;
        }
        await refresh();
        selected = project.working_node_id;
        render();
        if (result.status !== "committed")
          throw new Error(
            result.error ||
              "The edit was not committed. Restore a saved version before continuing.",
          );
      }
      activity(
        `${nodeLabel(project.working_node_id)} saved and verified. Compare the mood with your reference.`,
      );
    });
});
(async () => {
  try {
    const token = new URLSearchParams(location.hash.slice(1)).get("token");
    if (token) {
      history.replaceState(null, "", location.pathname);
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
      });
      if (!response.ok)
        throw new Error(
          "The launch link expired. Use the current private URL from your terminal.",
        );
    }
    await recent();
    const status = await api("/status");
    visionAvailable = status.vision_available;
    if (visionAvailable)
      $("#planner").append(new Option("OpenAI vision", "openai"));
    $("#vision-consent").disabled = !visionAvailable;
    $("#vision-status").textContent = visionAvailable
      ? `OpenAI ${status.vision_model} configured. Permission required per project.`
      : "To enable AI direction, set OPENAI_API_KEY before starting Lemon. Local analysis is ready without a key.";
    $("#editor-status").textContent = status.gimp_available
      ? "GIMP found · checking…"
      : "GIMP not installed";
    if (status.gimp_available) {
      const env = await api("/editor/check", {});
      $("#editor-status").textContent = `GIMP ${env.version} · Ready`;
    }
    const saved = localStorage.getItem("lemon-project");
    if (saved) {
      try {
        await openProject(saved);
      } catch {
        localStorage.removeItem("lemon-project");
      }
    }
  } catch (error) {
    notice(error.message);
    $("#editor-status").textContent = "Connection needs attention";
  }
})();
