const overviewTimestamp = document.querySelector("#overview-timestamp");
const overviewStats = document.querySelector("#overview-stats");
const latestSummary = document.querySelector("#latest-summary");
const reportsList = document.querySelector("#reports-list");
const hintsList = document.querySelector("#hints-list");
const artifactFeed = document.querySelector("#artifact-feed");
const latestRegistry = document.querySelector("#latest-registry");
const refreshButton = document.querySelector("#refresh-button");
const emptyStateTemplate = document.querySelector("#empty-state-template");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function safeUrl(value) {
  if (typeof value !== "string") {
    return "#";
  }

  if (value.startsWith("/") || value.startsWith("http://") || value.startsWith("https://")) {
    return value;
  }

  return "#";
}

function formatLocation(city, country) {
  return escapeHtml(country ? `${city}, ${country}` : city);
}

function formatDate(value) {
  if (!value) {
    return "Unknown time";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value ?? 0);
}

function renderEmptyState(target) {
  target.innerHTML = "";
  target.appendChild(emptyStateTemplate.content.cloneNode(true));
}

function renderStatCards(counts) {
  const items = [
    ["reports", counts.reports],
    ["summaries", counts.summaries],
    ["registries", counts.registries],
    ["hint files", counts.hints],
  ];

  overviewStats.innerHTML = items
    .map(
      ([label, value]) => `
        <div class="stat-card">
          <div class="stat-value">${formatNumber(value)}</div>
          <div class="stat-label">${escapeHtml(label)}</div>
        </div>
      `,
    )
    .join("");
}

function renderSummaryCard(summary) {
  if (!summary) {
    renderEmptyState(latestSummary);
    return;
  }

  const counts = summary.summary || {};
  const cities = (summary.cities || [])
    .slice(0, 8)
    .map(
      (city) => `
        <div class="city-card">
          <h3>${formatLocation(city.city, city.country)}</h3>
          <div class="pill-row">
            <span class="pill">accepted ${formatNumber(city.accepted)}</span>
            <span class="pill warning">rejected ${formatNumber(city.rejected)}</span>
          </div>
        </div>
      `,
    )
    .join("");

  const artifactLinks = Object.entries(summary.artifacts || {})
    .filter(([, link]) => link && link.url)
    .map(
      ([label, link]) =>
        `<a class="ghost-link" href="${safeUrl(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`,
    )
    .join("");

  latestSummary.innerHTML = `
    <article class="summary-card">
      <div class="summary-header">
        <div>
          <h3>${escapeHtml(summary.name)}</h3>
          <p class="meta-text">Generated ${escapeHtml(formatDate(summary.generated_at))}</p>
        </div>
        <a class="ghost-link" href="${safeUrl(summary.url)}" target="_blank" rel="noreferrer">open raw</a>
      </div>
      <div class="meta-grid">
        <div class="meta-cell">
          <div class="meta-label">new</div>
          <div class="meta-value">${formatNumber(counts.new)}</div>
        </div>
        <div class="meta-cell">
          <div class="meta-label">updated</div>
          <div class="meta-value">${formatNumber(counts.updated)}</div>
        </div>
        <div class="meta-cell">
          <div class="meta-label">unchanged</div>
          <div class="meta-value">${formatNumber(counts.unchanged)}</div>
        </div>
        <div class="meta-cell">
          <div class="meta-label">rejected</div>
          <div class="meta-value">${formatNumber(counts.rejected)}</div>
        </div>
      </div>
      <div class="link-row">${artifactLinks || ""}</div>
      <div class="city-grid">${cities || `<div class="empty-state"><p>No city rollup found.</p></div>`}</div>
    </article>
  `;
}

function renderReports(reports) {
  if (!reports.length) {
    renderEmptyState(reportsList);
    return;
  }

  reportsList.innerHTML = reports
    .map((report) => {
      const counts = report.summary || {};
      const cityCards = (report.cities || [])
        .slice(0, 6)
        .map(
          (city) => `
            <div class="city-card">
              <h3>${formatLocation(city.city, city.country)}</h3>
              <p class="meta-text">accepted ${formatNumber(city.accepted)} / rejected ${formatNumber(city.rejected)}</p>
            </div>
          `,
        )
        .join("");

      const spotlight = (report.project_spotlight || [])
        .map((project) => {
          const title = project.source_url
            ? `<a href="${safeUrl(project.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(project.title)}</a>`
            : escapeHtml(project.title);
          return `
            <div class="spotlight-item">
              <strong>${escapeHtml(project.city)}</strong>
              <p>${title}${project.status ? ` | ${escapeHtml(project.status)}` : ""}</p>
            </div>
          `;
        })
        .join("");

      const quickLinks = [report.registry, report.review, report.hints]
        .filter(Boolean)
        .map(
          (link) =>
            `<a class="ghost-link" href="${safeUrl(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.path.replace("runs/", ""))}</a>`,
        )
        .join("");

      return `
        <article class="artifact-card">
          <div class="artifact-header">
            <div>
              <h3 class="artifact-title">${escapeHtml(report.name)}</h3>
              <p class="meta-text">Generated ${escapeHtml(formatDate(report.generated_at))}</p>
            </div>
            <a class="ghost-link" href="${safeUrl(report.url)}" target="_blank" rel="noreferrer">open raw</a>
          </div>
          <div class="meta-grid">
            <div class="meta-cell">
              <div class="meta-label">cities</div>
              <div class="meta-value">${formatNumber(report.city_count)}</div>
            </div>
            <div class="meta-cell">
              <div class="meta-label">new</div>
              <div class="meta-value">${formatNumber(counts.new)}</div>
            </div>
            <div class="meta-cell">
              <div class="meta-label">updated</div>
              <div class="meta-value">${formatNumber(counts.updated)}</div>
            </div>
            <div class="meta-cell">
              <div class="meta-label">rejected</div>
              <div class="meta-value">${formatNumber(counts.rejected)}</div>
            </div>
          </div>
          <div class="link-row">${quickLinks}</div>
          <div class="city-grid">${cityCards}</div>
          ${
            spotlight
              ? `<div class="spotlight-list">${spotlight}</div>`
              : `<div class="empty-state"><p>No accepted project preview was found.</p></div>`
          }
        </article>
      `;
    })
    .join("");
}

function renderHints(hints) {
  if (!hints.length) {
    renderEmptyState(hintsList);
    return;
  }

  hintsList.innerHTML = hints
    .map((hintFile) => {
      const cityCards = (hintFile.cities || [])
        .slice(0, 10)
        .map((city) => {
          const candidateAdditions = city.candidate_additions || [];
          const omittedProjects = city.omitted_projects || [];
          const suspiciousRecords = city.suspicious_records || [];

          const additions = candidateAdditions.length
            ? candidateAdditions
                .map((item) => `<span class="chip">${escapeHtml(item.kind)}: ${escapeHtml(item.value)}</span>`)
                .join("")
            : '<span class="chip">no additions</span>';

          const omitted = omittedProjects.length
            ? omittedProjects
                .slice(0, 3)
                .map((item) => {
                  const title = item.url
                    ? `<a href="${safeUrl(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>`
                    : escapeHtml(item.title);
                  return `
                    <div class="hint-item">
                      <strong>${title}</strong>
                      ${item.notes ? `<p>${escapeHtml(item.notes)}</p>` : ""}
                    </div>
                  `;
                })
                .join("")
            : '<div class="hint-item"><strong>No likely omissions flagged.</strong></div>';

          const suspicious = suspiciousRecords.length
            ? suspiciousRecords
                .slice(0, 2)
                .map((item) => `<div class="hint-item warning"><strong>${escapeHtml(item.title)}</strong></div>`)
                .join("")
            : "";

          return `
            <div class="hint-city-card">
              <div class="hint-header">
                <h3>${formatLocation(city.city, city.country)}</h3>
                <span class="chip warning">${omittedProjects.length} omissions</span>
              </div>
              <div class="chip-row">${additions}</div>
              <div class="hint-list">${omitted}${suspicious}</div>
            </div>
          `;
        })
        .join("");

      const counts = hintFile.summary_counts || {};

      return `
        <article class="artifact-card">
          <div class="artifact-header">
            <div>
              <h3 class="artifact-title">${escapeHtml(hintFile.name)}</h3>
              <p class="meta-text">Generated ${escapeHtml(formatDate(hintFile.generated_at))}</p>
            </div>
            <a class="ghost-link" href="${safeUrl(hintFile.url)}" target="_blank" rel="noreferrer">open raw</a>
          </div>
          <div class="meta-grid">
            <div class="meta-cell">
              <div class="meta-label">cities</div>
              <div class="meta-value">${formatNumber(hintFile.city_count)}</div>
            </div>
            <div class="meta-cell">
              <div class="meta-label">additions</div>
              <div class="meta-value">${formatNumber(hintFile.suggestion_count)}</div>
            </div>
            <div class="meta-cell">
              <div class="meta-label">omitted</div>
              <div class="meta-value">${formatNumber(hintFile.omitted_count)}</div>
            </div>
            <div class="meta-cell">
              <div class="meta-label">accepted / rejected</div>
              <div class="meta-value">${formatNumber(counts.accepted)} / ${formatNumber(counts.rejected)}</div>
            </div>
          </div>
          <div class="hint-city-grid">${cityCards}</div>
        </article>
      `;
    })
    .join("");
}

function renderArtifactFeed(items) {
  if (!items.length) {
    renderEmptyState(artifactFeed);
    return;
  }

  artifactFeed.innerHTML = items
    .map(
      (item) => `
        <a class="artifact-feed-item" href="${safeUrl(item.url)}" target="_blank" rel="noreferrer">
          <div>
            <div><strong>${escapeHtml(item.name)}</strong></div>
            <div class="artifact-label">${escapeHtml(formatDate(item.generated_at))}</div>
          </div>
          <span class="artifact-tag">${escapeHtml(item.type)}</span>
        </a>
      `,
    )
    .join("");
}

function renderRegistry(registry) {
  if (!registry) {
    renderEmptyState(latestRegistry);
    return;
  }

  const breakdown = (registry.city_breakdown || [])
    .slice(0, 8)
    .map(
      (city) => `
        <div class="spotlight-item">
          <strong>${formatLocation(city.city, city.country)}</strong>
          <p>${formatNumber(city.count)} records</p>
        </div>
      `,
    )
    .join("");

  latestRegistry.innerHTML = `
    <article class="registry-card">
      <div class="registry-header">
        <div>
          <h3>${escapeHtml(registry.name)}</h3>
          <p class="meta-text">Generated ${escapeHtml(formatDate(registry.generated_at))}</p>
        </div>
        <a class="ghost-link" href="${safeUrl(registry.url)}" target="_blank" rel="noreferrer">open raw</a>
      </div>
      <div class="meta-grid">
        <div class="meta-cell">
          <div class="meta-label">records</div>
          <div class="meta-value">${formatNumber(registry.record_count)}</div>
        </div>
        <div class="meta-cell">
          <div class="meta-label">active</div>
          <div class="meta-value">${formatNumber(registry.active_count)}</div>
        </div>
      </div>
      <div class="spotlight-list">${breakdown}</div>
    </article>
  `;
}

async function loadDashboard() {
  refreshButton.disabled = true;
  overviewTimestamp.textContent = "Refreshing from runs/";

  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Dashboard request failed with ${response.status}`);
    }

    const data = await response.json();
    overviewTimestamp.textContent = `Refreshed ${formatDate(data.generated_at)}`;
    renderStatCards(data.artifact_counts || {});
    renderSummaryCard(data.latest_summary);
    renderReports(data.latest_reports || []);
    renderHints(data.latest_hints || []);
    renderArtifactFeed(data.recent_artifacts || []);
    renderRegistry(data.latest_registry);
  } catch (error) {
    overviewTimestamp.textContent = "Unable to load dashboard data";
    [latestSummary, reportsList, hintsList, artifactFeed, latestRegistry].forEach(renderEmptyState);
    console.error(error);
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", () => {
  loadDashboard();
});

loadDashboard();
