"""Interactive repository-backed dashboard for test prioritization."""

from v2.dashboard.components.header import render_header

PAGE_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job-bot | Priorização de testes com dados reais</title>
  <link rel="stylesheet" href="/style/dashboard.css">
</head>
<body class="predictive-page">
  <!-- SHARED_HEADER -->
  <div class="insights-shell">
    <aside class="insights-sidebar" aria-label="Navegação da qualidade">
      <div class="sidebar-brand"><span>JB</span><strong>Qualidade</strong></div>
      <nav>
        <a class="active" href="#overview">◈ <span>Visão geral</span></a>
        <a href="#areas">⌘ <span>Código</span></a>
        <a href="#flow-attention">▤ <span>Fluxos</span></a>
        <a href="#tests">✓ <span>Testes</span></a>
        <a href="#activity">▥ <span>Atividade</span></a>
        <a href="#references">≡ <span>Referências</span></a>
      </nav>
      <div class="sidebar-foot">Dados do repositório<br><span>Histórico Git · v2</span></div>
    </aside>

    <main id="overview" class="insights-main">
      <section class="predictive-intro">
        <div>
          <p class="eyebrow">QUALIDADE DE SOFTWARE · ATIVIDADE DO REPOSITÓRIO</p>
          <h1>Dashboard de qualidade e atividade do código</h1>
          <p>Áreas com mudanças recentes e arquivos de teste relacionados, observados no histórico Git deste projeto.</p>
        </div>
        <div class="intro-meta">
          <span id="data-source" class="demo-label"><span></span> Git real · carregando</span>
          <small id="last-updated" class="chart-caption" role="status"></small>
        </div>
      </section>

      <section class="predictive-controls" aria-label="Filtros da visualização">
        <label>Período
          <select id="period-filter">
            <option value="7">Últimos 7 dias</option>
            <option value="30" selected>Últimos 30 dias</option>
            <option value="90">Últimos 90 dias</option>
          </select>
        </label>
        <label>Área do código
          <select id="module-filter"><option value="all">Todas as áreas</option></select>
        </label>
        <button class="secondary" id="refresh-insights" type="button">↻ Atualizar</button>
      </section>

      <p id="insights-error" class="message error" role="alert" hidden></p>

      <section class="predictive-kpis" aria-label="Indicadores reais do repositório">
        <article class="predictive-kpi panel">
          <span class="kpi-icon risk-icon">↻</span>
          <div><p>Commits com código</p><strong id="kpi-commits">—</strong><small>no período selecionado</small></div>
        </article>
        <article class="predictive-kpi panel">
          <span class="kpi-icon failure-icon">⌘</span>
          <div><p>Arquivos de código alterados</p><strong id="kpi-files">—</strong><small>arquivos únicos em v2</small></div>
        </article>
        <article class="predictive-kpi panel">
          <span class="kpi-icon coverage-icon">▦</span>
          <div><p>Áreas modificadas</p><strong id="kpi-modules">—</strong><small>com alterações no período</small></div>
        </article>
        <article class="predictive-kpi panel coverage-kpi">
          <span class="kpi-icon tests-icon">✓</span>
          <div class="coverage-kpi-content">
            <p>Cobertura de código</p>
            <strong id="kpi-coverage">—</strong>
            <small id="coverage-details">Execute a suíte para medir</small>
            <small>Branches: <b id="kpi-branch-coverage">—</b></small>
          </div>
          <button id="measure-coverage" class="coverage-action secondary" type="button">Medir</button>
        </article>
      </section>
      <p id="coverage-status" class="coverage-status" role="status" aria-live="polite"></p>

      <section id="flow-attention" class="panel flow-attention-panel">
        <div class="section-heading">
          <div><p class="eyebrow">COBERTURA + MUDANÇAS RECENTES</p><h2>Mapa de atenção dos fluxos</h2></div>
          <div class="attention-legend"><span>Menos atenção</span><i></i><span>Mais atenção</span></div>
        </div>
        <p class="attention-explainer">Índice relativo = (1 + commits recentes + severidade histórica mapeada) × fração de linhas sem cobertura, normalizado de 0 a 100. É uma heurística explicável, não probabilidade de defeito.</p>
        <div class="risk-analysis-summary">
          <div>
            <p class="eyebrow">COBERTURA DE CENÁRIOS PONDERADA POR RISCO</p>
            <strong id="risk-weighted-coverage">—</strong>
            <small id="risk-weighted-details">Meça a cobertura para calcular</small>
          </div>
          <div>
            <p class="eyebrow">PREDIÇÃO DE DEFEITOS</p>
            <strong id="defect-prediction-value">Indisponível</strong>
            <small id="defect-prediction-details">Não há histórico confiável de defeitos mapeados a arquivos.</small>
          </div>
        </div>
        <p class="scenario-risk-explainer">Catálogo inicial revisável: a métrica cobre somente os cenários inventariados, não afirma completude dos requisitos. Cobertura de cenário = cenários do catálogo com todos os testes associados executados e aprovados ÷ total inventariado no módulo. Peso normalizado = risco bruto do módulo ÷ soma dos riscos incluídos; risco bruto = 1 + commits recentes + severidade dos defeitos mapeados. Cenários não medidos ficam N/D, nunca 100%.</p>
        <div id="scenario-risk-modules" class="scenario-risk-modules" aria-live="polite">
          <p class="empty">Cobertura por cenário será exibida após a medição.</p>
        </div>
        <div id="flow-attention-groups" class="flow-attention-groups">
          <p class="empty">Clique em “Medir” para comparar cobertura por linha, branch e atividade recente.</p>
        </div>
      </section>

      <section class="insights-panels">
        <article id="areas" class="panel compact-panel">
          <div class="section-heading priority-heading">
            <div><p class="eyebrow">ALTERAÇÕES RECENTES</p><h2>Áreas do código</h2></div>
            <label class="sort-control">Ordenar
              <select id="sort-filter">
                <option value="commits">Commits</option>
                <option value="files">Arquivos</option>
                <option value="tests">Testes</option>
              </select>
            </label>
          </div>
          <div class="table-wrap">
            <table class="priority-table">
              <thead><tr><th>Área</th><th>Commits</th><th>Arquivos</th><th>Testes</th></tr></thead>
              <tbody id="priority-rows"></tbody>
            </table>
          </div>
          <p id="table-empty" class="empty" hidden>Nenhuma área corresponde ao filtro selecionado.</p>
        </article>

        <article id="activity" class="panel compact-panel activity-panel">
          <div class="section-heading">
            <div><p class="eyebrow">MAPA DE ATIVIDADE</p><h2>Alterações por área</h2></div>
            <span class="chart-legend"><i></i> arquivos alterados</span>
          </div>
          <div id="activity-map" class="activity-map" aria-live="polite"></div>
          <div class="activity-legend"><span>Menos</span><i class="activity-low"></i><i class="activity-mid"></i><i class="activity-high"></i><span>Mais</span></div>
          <p class="chart-caption">A intensidade representa arquivos alterados no período, não risco de defeito.</p>
        </article>

        <article id="tests" class="panel compact-panel tests-panel">
          <div class="section-heading">
            <div><p class="eyebrow">TESTES EXISTENTES</p><h2>Associados às áreas</h2></div>
            <span id="test-count-label" class="chart-legend">— arquivos</span>
          </div>
          <div class="table-wrap">
            <table class="priority-table test-priority-table">
              <thead><tr><th>#</th><th>Arquivo de teste</th><th>Atividade</th></tr></thead>
              <tbody id="test-priority-rows"></tbody>
            </table>
          </div>
        </article>
      </section>

      <section class="panel timeline-panel">
        <div class="section-heading">
          <div><p class="eyebrow">HISTÓRICO GIT</p><h2>Commits com mudanças de código</h2></div>
          <span class="chart-legend"><i></i> commits por dia</span>
        </div>
        <div class="chart-wrap">
          <svg id="activity-chart" viewBox="0 0 760 250" role="img" aria-label="Gráfico de commits reais por data">
            <defs><linearGradient id="risk-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#60a5fa" stop-opacity=".28"/><stop offset="100%" stop-color="#60a5fa" stop-opacity="0"/></linearGradient></defs>
            <g class="chart-grid"><line x1="48" y1="30" x2="740" y2="30"/><line x1="48" y1="82" x2="740" y2="82"/><line x1="48" y1="134" x2="740" y2="134"/><line x1="48" y1="186" x2="740" y2="186"/></g>
            <g id="chart-y-axis" class="chart-axis"></g>
            <path id="chart-area" class="chart-area" d=""></path>
            <polyline id="chart-line" class="chart-line" points=""></polyline>
            <g id="chart-points"></g>
            <g id="chart-labels" class="chart-axis"></g>
          </svg>
        </div>
      </section>

      <section class="insights-info-grid">
        <article class="info-card">
          <h2>Como funciona</h2>
          <p>O painel lê commits recentes do histórico Git e agrupa arquivos Python por área do projeto.</p>
          <p>A cobertura mede linhas executáveis de código v2 alcançadas ao executar a suíte completa de testes v2.</p>
        </article>
        <article class="info-card">
          <h2>Sinais apresentados</h2>
          <ul><li>Commits com alterações de código</li><li>Arquivos Python únicos modificados</li><li>Arquivos de teste existentes por área</li></ul>
          <p class="info-callout">Atividade ajuda a orientar a revisão, mas não prova que o código apresenta defeitos.</p>
        </article>
        <article class="info-card">
          <h2>Benefícios</h2>
          <ul><li>Visibilidade das áreas mais ativas</li><li>Acesso rápido aos testes relacionados</li><li>Priorização transparente e baseada em dados reais</li></ul>
          <p class="info-callout">Não há histórico de defeitos ou execuções para estimar risco preditivo.</p>
        </article>
        <article id="references" class="info-card references-card">
          <h2>Referências</h2>
          <details>
            <summary>Bibliografia completa</summary>
            <ol>
              <li>MORAIS, I. S. de (Org.). <cite>Engenharia de software</cite>. São Paulo: Pearson, 2017. E-book.</li>
              <li>STEINER, J. <cite>Inteligência Artificial (IA) em testes de software</cite>. 2024. <a href="https://digital.ai/pt/catalyst-blog/ai-software-testing/" target="_blank" rel="noopener noreferrer">Digital.ai</a>. Acesso em: 5 mar. 2025.</li>
              <li>VERHAEG, R. <cite>Uma abordagem de predição de defeitos de software no contexto de desenvolvimento ágil</cite>. 2016. Dissertação (Mestrado) — ICMC, Universidade de São Paulo. <a href="https://www.teses.usp.br/teses/disponiveis/55/55134/tde-19122016-110134/pt-br.php" target="_blank" rel="noopener noreferrer">Tese USP</a>.</li>
              <li>PONTES, A. B. <cite>Uso de predição de defeitos aplicada ao processo de identificação e recomendação para priorização de bugs</cite>. 2017. Dissertação (Mestrado) — Universidade Federal da Paraíba. <a href="https://repositorio.ufpb.br/jspui/handle/123456789/12907?locale=pt_BR" target="_blank" rel="noopener noreferrer">Repositório UFPB</a>.</li>
              <li>FRANCO, V. O.; ARAÚJO, M. A. P. Análise preditiva de tendência a falha em módulos de software utilizando programação genética. <cite>Revista BSI</cite>, v. 6, n. 1, p. 1–21, 2020.</li>
            </ol>
          </details>
        </article>
      </section>
    </main>
  </div>
  <script>
    const periodFilter = document.getElementById("period-filter");
    const moduleFilter = document.getElementById("module-filter");
    const sortFilter = document.getElementById("sort-filter");
    let insights = null;

    function selectedModules() {
      return insights.modules.filter(item => moduleFilter.value === "all" || item.id === moduleFilter.value);
    }

    function renderChart(trend) {
      const values = trend.map(item => item.commits);
      const maxValue = Math.max(1, ...values);
      const points = values.map((value, index) => [
        50 + index * (680 / Math.max(1, values.length - 1)),
        186 - value / maxValue * 156
      ]);
      document.getElementById("chart-line").setAttribute("points", points.map(point => point.join(",")).join(" "));
      document.getElementById("chart-area").setAttribute("d", points.length
        ? `M ${points[0][0]} 186 L ${points.map(point => point.join(" ")).join(" L ")} L ${points[points.length - 1][0]} 186 Z`
        : "");
      document.getElementById("chart-points").replaceChildren(...points.map(([x, y], index) => {
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", x);
        circle.setAttribute("cy", y);
        circle.setAttribute("r", values.length > 30 ? "2" : "3.5");
        circle.setAttribute("class", "chart-point");
        circle.setAttribute("aria-label", `${trend[index].date}: ${trend[index].commits} commits`);
        return circle;
      }));
      const axisLabels = [maxValue, Math.round(maxValue * 2 / 3), Math.round(maxValue / 3), 0]
        .filter((value, index, list) => list.indexOf(value) === index);
      document.getElementById("chart-y-axis").replaceChildren(...axisLabels.map((value, index) => {
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", "38");
        text.setAttribute("y", `${34 + index * 52}`);
        text.setAttribute("text-anchor", "end");
        text.textContent = value;
        return text;
      }));
      const labelIndexes = [...new Set([0, Math.round((values.length - 1) / 3), Math.round((values.length - 1) * 2 / 3), values.length - 1])];
      document.getElementById("chart-labels").replaceChildren(...labelIndexes.map(index => {
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", `${50 + index * (680 / Math.max(1, values.length - 1))}`);
        text.setAttribute("y", "222");
        text.setAttribute("text-anchor", index === 0 ? "start" : index === values.length - 1 ? "end" : "middle");
        text.textContent = trend[index].date.slice(5);
        return text;
      }));
    }

    function renderTable(data) {
      const sortKey = { commits: "commits", files: "files_changed", tests: "test_file_count" }[sortFilter.value];
      data.sort((a, b) => b[sortKey] - a[sortKey] || a.name.localeCompare(b.name));
      const rows = data.map(item => {
        const row = document.createElement("tr");
        const cells = [
          ["module-name", item.name],
          ["", item.commits],
          ["", item.files_changed],
          ["", item.test_file_count]
        ];
        cells.forEach(([className, value]) => {
          const cell = document.createElement("td");
          cell.className = className;
          cell.textContent = value;
          row.appendChild(cell);
        });
        return row;
      });
      document.getElementById("priority-rows").replaceChildren(...rows);
      document.getElementById("table-empty").hidden = data.length > 0;
    }

    function renderActivityMap(data) {
      const maxFiles = Math.max(1, ...data.map(item => item.files_changed));
      const rows = [...data]
        .sort((a, b) => b.files_changed - a.files_changed || a.name.localeCompare(b.name))
        .map(item => {
          const row = document.createElement("div");
          row.className = "activity-row";
          const name = document.createElement("div");
          name.className = "activity-name";
          const folder = document.createElement("span");
          folder.className = "activity-folder";
          folder.textContent = item.id === "cli" ? "ƒ" : "▸";
          const label = document.createElement("span");
          label.textContent = item.name;
          const path = document.createElement("small");
          path.textContent = item.path;
          name.append(folder, label, path);

          const meter = document.createElement("div");
          meter.className = "activity-meter";
          const fill = document.createElement("span");
          fill.style.setProperty("--activity", `${Math.max(3, item.files_changed / maxFiles * 100)}%`);
          fill.className = item.files_changed / maxFiles > 0.66
            ? "activity-high"
            : item.files_changed / maxFiles > 0.33 ? "activity-mid" : "activity-low";
          meter.appendChild(fill);

          const count = document.createElement("strong");
          count.textContent = item.files_changed;
          row.append(name, meter, count);
          return row;
        });
      document.getElementById("activity-map").replaceChildren(...rows);
    }

    function renderTestPriority(data) {
      const tests = data.flatMap(item => item.test_files.map(file => ({
        file,
        module: item.name,
        commits: item.commits
      }))).sort((a, b) => b.commits - a.commits || a.file.localeCompare(b.file));
      const rows = tests.slice(0, 8).map((test, index) => {
        const row = document.createElement("tr");
        const rank = document.createElement("td");
        rank.textContent = index + 1;
        const fileCell = document.createElement("td");
        fileCell.className = "test-file-cell";
        const file = document.createElement("strong");
        file.textContent = test.file;
        const area = document.createElement("small");
        area.textContent = test.module;
        fileCell.append(file, area);
        const activity = document.createElement("td");
        activity.textContent = `${test.commits} commits`;
        row.append(rank, fileCell, activity);
        return row;
      });
      document.getElementById("test-priority-rows").replaceChildren(...rows);
      document.getElementById("test-count-label").textContent = `${tests.length} arquivos`;
    }

    function renderFlowAttention(flows) {
      const container = document.getElementById("flow-attention-groups");
      const moduleById = new Map(insights.modules.map(item => [item.id, item]));
      const groups = flows.map(flow => {
        const activity = moduleById.get(flow.id);
        const files = flow.files.map(file => {
          const commits = activity?.file_commits[file.path] || 0;
          return { ...file, commits, uncovered: 100 - file.coverage_percent };
        }).sort((a, b) =>
          (b.heuristic_risk_score || 0) - (a.heuristic_risk_score || 0) ||
          a.coverage_percent - b.coverage_percent ||
          b.commits - a.commits ||
          a.path.localeCompare(b.path)
        );
        return { ...flow, files };
      }).sort((a, b) =>
        a.coverage_percent - b.coverage_percent ||
        b.files.filter(file => file.commits > 0).length -
          a.files.filter(file => file.commits > 0).length
      );

      container.replaceChildren(...groups.map(flow => {
        const group = document.createElement("article");
        group.className = "flow-attention-group";
        const heading = document.createElement("div");
        heading.className = "flow-attention-heading";
        const title = document.createElement("h3");
        title.textContent = flow.name;
        const summary = document.createElement("strong");
        summary.textContent = `${flow.coverage_percent}% linhas`;
        heading.append(title, summary);

        const description = document.createElement("p");
        const changedFiles = flow.files.filter(file => file.commits > 0).length;
        description.textContent =
          `${flow.covered_lines} de ${flow.total_lines} linhas cobertas · ` +
          `${flow.branch_coverage_percent === null ? "branches N/D" : `${flow.branch_coverage_percent}% branches`} · ` +
          `${changedFiles} ${changedFiles === 1 ? "arquivo alterado" : "arquivos alterados"} no período`;

        const fileRows = document.createElement("div");
        fileRows.className = "flow-attention-files";
        flow.files.forEach(file => {
          const row = document.createElement("div");
          row.className = "flow-attention-file";
          const metadata = document.createElement("div");
          metadata.className = "flow-attention-file-meta";
          const path = document.createElement("span");
          path.className = "flow-attention-path";
          path.textContent = file.path.replace(`v2/flows/${flow.id}/`, "");
          path.title = file.path;
          const coverage = document.createElement("strong");
          const branchCoverage = file.branch_coverage_percent === null
            ? "N/D"
            : `${file.branch_coverage_percent}%`;
          const riskScore = file.heuristic_risk_score === null
            ? "N/D"
            : `${file.heuristic_risk_score}/100`;
          coverage.textContent = file.total_lines
            ? `L ${file.coverage_percent}% · B ${branchCoverage}`
            : "N/D";
          metadata.append(path, coverage);

          const bar = document.createElement("div");
          bar.className = "attention-meter";
          bar.setAttribute("role", "img");
          bar.setAttribute(
            "aria-label",
            file.total_lines
              ? `Índice heurístico ${riskScore}; ${file.coverage_percent}% das linhas cobertas; ${branchCoverage} dos branches cobertos; ${file.commits} commits no período; ${file.historical_defects} defeitos mapeados`
              : `Sem linhas executáveis mensuráveis; ${file.commits} commits no período`
          );
          const uncovered = document.createElement("span");
          uncovered.style.setProperty("--uncovered", `${file.uncovered}%`);
          bar.appendChild(uncovered);

          const detail = document.createElement("small");
          const commitLabel = file.commits === 1 ? "commit" : "commits";
          detail.textContent = file.total_lines
            ? `${file.total_lines - file.covered_lines} linhas sem cobertura · índice ${riskScore} · ${file.commits} ${commitLabel} · ${file.historical_defects} defeitos mapeados`
            : `Sem linhas executáveis · ${file.commits} ${commitLabel}`;
          row.append(metadata, bar, detail);
          fileRows.appendChild(row);
        });
        group.append(heading, description, fileRows);
        return group;
      }));
    }

    function updateDashboard() {
      if (!insights) return;
      const data = selectedModules();
      const selectedModule = data.length === 1 ? data[0] : null;
      const commits = selectedModule
        ? selectedModule.commits
        : insights.summary.commits;
      document.getElementById("kpi-commits").textContent = commits;
      document.getElementById("kpi-files").textContent = selectedModule
        ? selectedModule.files_changed
        : insights.summary.files_changed;
      document.getElementById("kpi-modules").textContent = data.filter(item => item.commits > 0).length;
      const trend = selectedModule
        ? insights.trend.map((item, index) => ({ date: item.date, commits: selectedModule.trend[index] }))
        : insights.trend;
      renderChart(trend);
      renderTable(data);
      renderActivityMap(data);
      renderTestPriority(data);
    }

    function renderScenarioRiskCoverage(coverage) {
      const container = document.getElementById("scenario-risk-modules");
      if (!coverage.modules.length) {
        const message = document.createElement("p");
        message.className = "empty";
        message.textContent = coverage.reason || "Cobertura de cenários indisponível.";
        container.replaceChildren(message);
        return;
      }
      const rows = coverage.modules.map(module => {
        const row = document.createElement("div");
        row.className = "scenario-risk-row";
        const heading = document.createElement("div");
        heading.className = "scenario-risk-heading";
        const name = document.createElement("strong");
        name.textContent = module.name;
        const values = document.createElement("span");
        values.textContent =
          `${module.covered_scenarios}/${module.total_scenarios} cenários · ` +
          `${module.scenario_coverage_percent}% · ` +
          `${module.risk_weight_percent === null ? "peso N/D" : `peso ${module.risk_weight_percent}%`}`;
        heading.append(name, values);
        const meter = document.createElement("div");
        meter.className = "scenario-risk-meter";
        meter.setAttribute("role", "img");
        meter.setAttribute(
          "aria-label",
          `${module.name}: ${module.scenario_coverage_percent}% dos cenários cobertos, ` +
          `peso de risco normalizado ${module.risk_weight_percent}%`
        );
        const fill = document.createElement("span");
        fill.style.setProperty("--scenario-coverage", `${module.scenario_coverage_percent}%`);
        meter.appendChild(fill);
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = "Ver cenários inventariados";
        const list = document.createElement("ul");
        module.scenarios.forEach(scenario => {
          const item = document.createElement("li");
          item.textContent = `${scenario.status === "covered" ? "Coberto" : "Não coberto"} · ${scenario.name}`;
          list.appendChild(item);
        });
        details.append(summary, list);
        row.append(heading, meter, details);
        return row;
      });
      if (coverage.excluded_modules.length) {
        const unknown = document.createElement("p");
        unknown.className = "scenario-risk-missing";
        unknown.textContent = coverage.excluded_modules
          .map(module => `${module.name}: N/D (${module.reason})`)
          .join(" · ");
        rows.push(unknown);
      }
      container.replaceChildren(...rows);
    }

    async function measureCoverage() {
      const button = document.getElementById("measure-coverage");
      const status = document.getElementById("coverage-status");
      button.disabled = true;
      button.textContent = "Medindo…";
      status.className = "coverage-status";
      status.textContent = "Executando a suíte v2 e medindo cobertura de cenários, linhas e branches…";
      try {
        const response = await fetch(`/api/test-coverage?days=${periodFilter.value}`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Não foi possível medir a cobertura.");
        document.getElementById("kpi-coverage").textContent = `${result.coverage_percent}%`;
        document.getElementById("coverage-details").textContent =
          `${result.covered_lines} de ${result.total_lines} linhas · ${result.coverage_tool} ${result.coverage_tool_version}`;
        document.getElementById("kpi-branch-coverage").textContent =
          result.branch_coverage_percent === null
            ? "N/D"
            : `${result.branch_coverage_percent}% (${result.covered_branches}/${result.total_branches})`;
        const testStatus = `${result.tests_run} testes executados · ${result.test_failures} falhas · ${result.test_errors} erros`;
        renderFlowAttention(result.flows);
        const scenarioCoverage = result.risk_weighted_scenario_coverage;
        document.getElementById("risk-weighted-coverage").textContent =
          scenarioCoverage.status === "available"
            ? `${scenarioCoverage.coverage_percent}%`
            : "N/D";
        document.getElementById("risk-weighted-details").textContent =
          scenarioCoverage.status === "available"
            ? `${scenarioCoverage.measured_modules} módulos · peso normalizado por risco` +
              (scenarioCoverage.missing_risk_inputs.length
                ? ` · ausente: ${scenarioCoverage.missing_risk_inputs.join(", ")}`
                : "")
            : scenarioCoverage.reason || "Cobertura de cenários indisponível";
        renderScenarioRiskCoverage(scenarioCoverage);
        document.getElementById("defect-prediction-value").textContent =
          result.defect_prediction.status === "available" ? "Experimental" : "Indisponível";
        const defectHistory = result.defect_history;
        const historySummary = defectHistory.status === "available"
          ? `${defectHistory.mapped_defects} defeitos mapeados a arquivos por PRs`
          : defectHistory.reason;
        document.getElementById("defect-prediction-details").textContent =
          `${result.defect_prediction.reason} GitHub: ${historySummary}`;
        status.className = result.test_failures || result.test_errors
          ? "coverage-status error"
          : "coverage-status success";
        const failedTestDetails = result.test_issues.length
          ? ` · ${result.test_issues.map(issue => `${issue.test}: ${issue.detail}`).join("; ")}`
          : "";
        status.textContent = `${testStatus}${failedTestDetails} · medido em ${new Date(result.generated_at).toLocaleString("pt-BR")}`;
      } catch (error) {
        document.getElementById("kpi-coverage").textContent = "—";
        document.getElementById("coverage-details").textContent = "Medição indisponível";
        document.getElementById("kpi-branch-coverage").textContent = "—";
        document.getElementById("risk-weighted-coverage").textContent = "N/D";
        document.getElementById("risk-weighted-details").textContent = "Medição indisponível";
        document.getElementById("scenario-risk-modules").replaceChildren();
        document.getElementById("flow-attention-groups").replaceChildren();
        status.className = "coverage-status error";
        status.textContent = error.message || "Não foi possível medir a cobertura.";
      } finally {
        button.disabled = false;
        button.textContent = "Medir";
      }
    }

    async function loadInsights() {
      const button = document.getElementById("refresh-insights");
      const error = document.getElementById("insights-error");
      button.disabled = true;
      error.hidden = true;
      try {
        const response = await fetch(`/api/test-insights?days=${periodFilter.value}`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Não foi possível carregar o histórico Git.");
        insights = result;
        const selected = moduleFilter.value;
        moduleFilter.replaceChildren(new Option("Todas as áreas", "all"));
        insights.modules.forEach(item => moduleFilter.add(new Option(item.name, item.id)));
        moduleFilter.value = insights.modules.some(item => item.id === selected) ? selected : "all";
        const source = document.getElementById("data-source");
        source.lastChild.textContent = " Git real · atualizado";
        document.getElementById("last-updated").textContent =
          `Atualizado em ${new Date(insights.generated_at).toLocaleString("pt-BR")}`;
        updateDashboard();
      } catch (loadError) {
        insights = null;
        error.textContent = loadError.message || "Não foi possível carregar o histórico Git.";
        error.hidden = false;
        document.getElementById("data-source").lastChild.textContent = " Git indisponível";
        ["kpi-commits", "kpi-files", "kpi-modules"].forEach(id => {
          document.getElementById(id).textContent = "—";
        });
        document.getElementById("priority-rows").replaceChildren();
        document.getElementById("activity-map").replaceChildren();
        document.getElementById("test-priority-rows").replaceChildren();
        document.getElementById("test-count-label").textContent = "— arquivos";
        document.getElementById("table-empty").hidden = false;
        document.getElementById("chart-line").setAttribute("points", "");
        document.getElementById("chart-area").setAttribute("d", "");
        document.getElementById("chart-points").replaceChildren();
        document.getElementById("chart-labels").replaceChildren();
        document.getElementById("chart-y-axis").replaceChildren();
      } finally {
        button.disabled = false;
      }
    }

    periodFilter.addEventListener("change", loadInsights);
    moduleFilter.addEventListener("change", updateDashboard);
    sortFilter.addEventListener("change", updateDashboard);
    document.getElementById("refresh-insights").addEventListener("click", loadInsights);
    document.getElementById("measure-coverage").addEventListener("click", measureCoverage);
    document.querySelectorAll(".insights-sidebar nav a").forEach(link => {
      link.addEventListener("click", () => {
        const activeLink = document.querySelector(".insights-sidebar nav a.active");
        if (activeLink) activeLink.classList.remove("active");
        link.classList.add("active");
      });
    });
    loadInsights();
  </script>
</body>
</html>
"""

PAGE_HTML = PAGE_HTML.replace("<!-- SHARED_HEADER -->", render_header("test-insights"))
