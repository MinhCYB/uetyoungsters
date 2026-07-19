const stageLabels = {
  initial: "Hồ sơ ban đầu",
  analyzed: "Đã phân tích",
  planned: "Đã có kế hoạch",
  advanced: "Đã cập nhật T1",
};

const skillLabels = {
  SKILL_TRIG_TRANSFORMATION: "Biến đổi lượng giác",
  SKILL_PROBABILITY: "Xác suất",
  SKILL_DATA_REASONING: "Suy luận dữ liệu",
  SKILL_DECISION_MAKING: "Ra quyết định",
};

const careerLabels = {
  CAREER_GROUP_DATA_AI: "Data/AI",
  CAREER_GROUP_ECONOMICS: "Kinh tế",
};

const gapLabels = {
  academic: "Khoảng trống học tập",
  exploration: "Khoảng trống trải nghiệm",
  decision: "Khoảng trống ra quyết định",
};

const priorityLabels = {
  high: "Cao",
  medium: "Trung bình",
  low: "Thấp",
};

const evidenceSourceLabels = {
  assessment: "Bài kiểm tra",
  academic_record: "Kết quả học tập",
  teacher_observation: "Nhận xét giáo viên",
  self_report: "Tự đánh giá",
  activity_result: "Hoạt động trải nghiệm",
};

const marketModeLabels = {
  pipeline_export: "Dữ liệu từ pipeline thị trường",
  fallback_demo: "Dữ liệu dự phòng cho demo",
};

const outcomeLabels = {
  meaningful_improvement: "Cải thiện rõ rệt",
  partial_improvement: "Có cải thiện",
  no_meaningful_change: "Chưa thay đổi đáng kể",
  regression: "Có dấu hiệu giảm",
};

const elements = {
  stage: document.querySelector("#stage-badge"),
  name: document.querySelector("#student-name"),
  profile: document.querySelector("#profile-facts"),
  weeklyFocus: document.querySelector("#weekly-focus"),
  analyze: document.querySelector("#analyze-button"),
  plan: document.querySelector("#plan-button"),
  advance: document.querySelector("#advance-button"),
  reset: document.querySelector("#reset-button"),
  loading: document.querySelector("#loading-message"),
  error: document.querySelector("#error-banner"),
  success: document.querySelector("#success-banner"),
  insightSection: document.querySelector("#insight-section"),
  strengths: document.querySelector("#strengths-grid"),
  gaps: document.querySelector("#gaps-grid"),
  market: document.querySelector("#market-context"),
  planSection: document.querySelector("#plan-section"),
  planTotal: document.querySelector("#plan-total"),
  tasks: document.querySelector("#plan-tasks"),
  comparisonSection: document.querySelector("#comparison-section"),
  comparison: document.querySelector("#comparison-grid"),
  nextStep: document.querySelector("#next-step"),
  debug: document.querySelector("#debug-json"),
};

let currentState = null;
let loading = false;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function request(path, method = "GET") {
  setLoading(true);
  clearBanners();
  try {
    const response = await fetch(path, { method, headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || `Yêu cầu thất bại (${response.status})`);
    currentState = payload;
    render(payload);
    return payload;
  } catch (error) {
    showError(error instanceof Error ? error.message : "Không thể kết nối local API.");
    throw error;
  } finally {
    setLoading(false);
  }
}

function setLoading(value) {
  loading = value;
  elements.loading.hidden = !value;
  updateButtons();
}

function clearBanners() {
  elements.error.hidden = true;
  elements.success.hidden = true;
}

function showError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
}

function showSuccess(message) {
  elements.success.textContent = message;
  elements.success.hidden = false;
}

function updateButtons() {
  const stage = currentState?.stage;
  elements.analyze.disabled = loading || stage !== "initial";
  elements.plan.disabled = loading || stage !== "analyzed";
  elements.advance.disabled = loading || stage !== "planned";
  elements.reset.disabled = loading;
}

function render(state) {
  const student = state.student;
  elements.stage.textContent = stageLabels[state.stage] || "Đang cập nhật";
  elements.name.textContent = student.display_name;
  elements.weeklyFocus.textContent = student.weekly_available_minutes;
  elements.profile.innerHTML = [
    `Lớp ${student.grade_level}`,
    `${student.weekly_available_minutes} phút mỗi tuần`,
    ...student.career_interest_ids.map((id) => careerLabels[id] || "Hướng nghề quan tâm"),
    student.exam_week ? "Đang trong tuần thi" : "Không phải tuần thi",
  ].map((item) => `<span>${escapeHtml(item)}</span>`).join("");

  const analyzed = state.stage !== "initial";
  elements.insightSection.hidden = !analyzed;
  if (analyzed) renderInsights(state);

  const planned = state.stage === "planned" || state.stage === "advanced";
  elements.planSection.hidden = !planned;
  if (planned) renderPlan(state.weekly_plan);

  const advanced = state.stage === "advanced";
  elements.comparisonSection.hidden = !advanced;
  if (advanced) renderComparison(state.comparison);

  elements.debug.textContent = JSON.stringify(state, null, 2);
  updateButtons();
}

function renderInsights(state) {
  const evidenceById = new Map(state.evidence.map((item) => [item.evidence_id, item]));
  const strengths = [...state.ability_profile]
    .filter((item) => item.estimated_level >= 0.65)
    .sort((a, b) => b.estimated_level - a.estimated_level);
  elements.strengths.innerHTML = strengths.map((item) => {
    const percentage = Math.round(item.estimated_level * 100);
    return `<article class="strength-card">
      <strong>${escapeHtml(skillLabels[item.skill_id] || "Kỹ năng nền tảng")}</strong>
      <div class="meter" aria-label="Mức ước lượng ${percentage}%"><span style="width:${percentage}%"></span></div>
      <small>${percentage}% · độ tin cậy ${Math.round(item.confidence * 100)}%</small>
    </article>`;
  }).join("") || "<p>Chưa đủ bằng chứng để xác định điểm mạnh.</p>";

  elements.gaps.innerHTML = state.gaps.map((gap) => {
    const subject = gap.skill_id
      ? skillLabels[gap.skill_id] || "Kỹ năng nền tảng"
      : gap.career_group_ids.map((id) => careerLabels[id] || "Hướng nghề").join(" ↔ ");
    const sources = [...new Set(gap.evidence_ids
      .map((id) => evidenceById.get(id)?.source_type)
      .filter(Boolean))];
    const sourceChips = sources.length
      ? sources.map((source) => `<span>${escapeHtml(evidenceSourceLabels[source] || "Nguồn khác")}</span>`).join("")
      : "<span>Chưa có bằng chứng trải nghiệm</span>";
    const priority = priorityLabels[gap.priority] || "Chưa xác định";
    return `<article class="gap-card ${escapeHtml(gap.gap_type)}">
      <p class="eyebrow">${escapeHtml(gapLabels[gap.gap_type] || gap.gap_type)}</p>
      <h3>${escapeHtml(subject)}</h3>
      <p>${escapeHtml(gapReason(gap))}</p>
      <div class="gap-meta">
        <span>${gap.evidence_ids.length} bằng chứng</span>
        <span class="priority priority-${escapeHtml(gap.priority)}">Ưu tiên: ${escapeHtml(priority)}</span>
      </div>
      <div class="source-chips" aria-label="Nguồn bằng chứng">${sourceChips}</div>
    </article>`;
  }).join("");

  elements.market.innerHTML = state.market.map((item) => `<article class="market-card">
    <h3>${escapeHtml(item.display_name)}</h3>
    <p>${escapeHtml(marketDescription(item))}</p>
    <small>Nguồn: ${escapeHtml(marketModeLabels[item.data_mode] || "Nguồn dữ liệu nội bộ")} · ${item.sample_size} mẫu</small>
    ${item.sample_size < 5 ? '<p class="sample-note">Quy mô mẫu còn nhỏ, chỉ dùng làm tín hiệu tham khảo trong demo.</p>' : ""}
  </article>`).join("");
}

function gapReason(gap) {
  if (gap.gap_type === "academic") {
    return "Các kết quả học tập hiện tại cho thấy nội dung này vẫn thấp hơn ngưỡng nền tảng cần thiết.";
  }
  if (gap.gap_type === "exploration") {
    const career = careerLabels[gap.career_group_ids[0]] || "Hướng nghề này";
    return `${career} chưa có micro-experience đủ mạnh để kiểm chứng mức hứng thú và cách làm việc thực tế.`;
  }
  return "Minh Anh chưa có đủ trải nghiệm ở cả hai hướng để so sánh và thu hẹp lựa chọn một cách có căn cứ.";
}

function marketDescription(item) {
  if (item.career_group_id === "CAREER_GROUP_DATA_AI") {
    return `Snapshot hiện tại có ${item.sample_size} tin tuyển dụng thuộc nhóm Phân tích dữ liệu và Phân tích nghiệp vụ.`;
  }
  if (item.career_group_id === "CAREER_GROUP_ECONOMICS") {
    return `Snapshot hiện tại có ${item.sample_size} tin tuyển dụng thuộc nhóm Kế toán, Phân tích rủi ro tín dụng và Phát triển kinh doanh.`;
  }
  return `Snapshot hiện tại có ${item.sample_size} tín hiệu thị trường cho nhóm nghề này.`;
}

function renderPlan(plan) {
  elements.planTotal.textContent = `${plan.total_planned_minutes}/${plan.weekly_budget_minutes} phút`;
  elements.tasks.innerHTML = plan.tasks.map((task, index) => `<article class="task-item">
    <span class="task-number">0${index + 1}</span>
    <div>
      <h3>${escapeHtml(task.title)}</h3>
      <p>${escapeHtml(taskReason(task))}</p>
    </div>
    <strong class="task-minutes">${task.estimated_minutes} phút</strong>
  </article>`).join("");
}

function taskReason(task) {
  if (task.skill_id === "SKILL_TRIG_TRANSFORMATION") {
    return "Kết quả học tập và bài kiểm tra cho thấy đây là nội dung cần ưu tiên.";
  }
  if (task.career_group_id === "CAREER_GROUP_DATA_AI") {
    return "Em quan tâm Data/AI nhưng chưa có trải nghiệm thực hành để kiểm chứng.";
  }
  if (task.career_group_id === "CAREER_GROUP_ECONOMICS") {
    return "Em cần thêm một trải nghiệm Kinh tế để có cơ sở so sánh hai hướng quan tâm.";
  }
  return "Nhiệm vụ này được chọn từ khoảng trống ưu tiên hiện tại.";
}

function renderComparison(comparison) {
  const outcomes = comparison.after.outcomes;
  const trig = outcomes.find((item) => item.metric_type === "SKILL_TRIG_TRANSFORMATION");
  const assessment = comparison.assessment_result;
  const interest = outcomes.find((item) => item.metric_type === "INTEREST_CAREER_GROUP_DATA_AI");
  const activity = comparison.activity_result;
  const beforeDataGap = comparison.before.gaps.some((gap) => gap.gap_type === "exploration" && gap.career_group_ids.includes("CAREER_GROUP_DATA_AI"));
  const afterDataGap = comparison.after.gaps.some((gap) => gap.gap_type === "exploration" && gap.career_group_ids.includes("CAREER_GROUP_DATA_AI"));
  const decisionRemains = comparison.after.gaps.some((gap) => gap.gap_type === "decision");
  const cards = [];

  if (trig && assessment) cards.push(`<article class="outcome-card">
    <p class="eyebrow">LƯỢNG GIÁC</p>
    <div class="value-line"><span>${formatRaw(assessment.before_score)}/${formatRaw(assessment.before_max_score)}</span><span class="arrow">→</span><span>${formatRaw(assessment.after_score)}/${formatRaw(assessment.after_max_score)}</span></div>
    <span class="status-good">${escapeHtml(outcomeLabels[trig.status] || "Đã cập nhật")}</span>
  </article>`);

  cards.push(`<article class="outcome-card">
    <p class="eyebrow">DATA MICRO-EXPERIENCE</p>
    <div class="value-line"><span>${formatRaw(activity.rubric_score)}/${formatRaw(activity.max_score)}</span></div>
    <span class="status-good">Đã hoàn thành · ${escapeHtml(activity.preferred_part || "Có phản hồi")}</span>
  </article>`);

  if (interest) cards.push(`<article class="outcome-card">
    <p class="eyebrow">HỨNG THÚ DATA/AI</p>
    <div class="value-line"><span>${formatScore(interest.before_value, activity.interest_max_score)}</span><span class="arrow">→</span><span>${formatScore(interest.after_value, activity.interest_max_score)}</span></div>
    <span class="status-good">${escapeHtml(outcomeLabels[interest.status] || "Đã cập nhật")}</span>
  </article>`);

  cards.push(`<article class="outcome-card">
    <p class="eyebrow">KHOẢNG TRỐNG KHÁM PHÁ</p>
    <div class="value-line"><span>${beforeDataGap ? "Có" : "Không"}</span><span class="arrow">→</span><span>${afterDataGap ? "Còn" : "Đã đóng"}</span></div>
    <span class="${decisionRemains ? "status-open" : "status-good"}">${decisionRemains ? "Khoảng trống ra quyết định vẫn còn — chưa kết luận nghề" : "Đã đủ bằng chứng so sánh"}</span>
  </article>`);

  elements.comparison.innerHTML = cards.join("");
  const next = comparison.next_step;
  elements.nextStep.innerHTML = next ? `<h3>Bước tiếp theo: ${escapeHtml(next.title)}</h3>
    <p>${escapeHtml(nextStepDescription(next))}</p>` : "";
}

function nextStepDescription(next) {
  const career = careerLabels[next.career_group_id] || "Hướng nghề tiếp theo";
  if (next.career_group_id === "CAREER_GROUP_ECONOMICS") {
    return `${career} · ${next.estimated_minutes} phút. Em chưa có trải nghiệm thực hành về Kinh tế, nên hoạt động này sẽ giúp tạo thêm bằng chứng để so sánh với hướng Data/AI.`;
  }
  if (next.career_group_id === "CAREER_GROUP_DATA_AI") {
    return `${career} · ${next.estimated_minutes} phút. Em chưa có trải nghiệm thực hành về Data/AI, nên hoạt động này sẽ giúp kiểm chứng mức hứng thú bằng một nhiệm vụ cụ thể.`;
  }
  return `${career} · ${next.estimated_minutes} phút. Hoạt động này sẽ bổ sung bằng chứng cho lần cập nhật tiếp theo.`;
}

function formatScore(value, scale) {
  return `${formatRaw(value * scale)}/${formatRaw(scale)}`;
}

function formatRaw(value) {
  return Number.isInteger(value) ? String(value) : Number(value).toFixed(1).replace(".0", "");
}

async function runAction(path, successMessage) {
  try {
    await request(path, "POST");
    showSuccess(successMessage);
  } catch (_) {
    // request() already presents the actionable error to the user.
  }
}

elements.analyze.addEventListener("click", () => runAction("/api/demo/analyze", "Đã phân tích hồ sơ từ bằng chứng T0."));
elements.plan.addEventListener("click", () => runAction("/api/demo/plan", "Đã tạo kế hoạch tuần trong ngân sách thời gian."));
elements.advance.addEventListener("click", () => runAction("/api/demo/advance", "Đã cập nhật snapshot sau hai tuần."));
elements.reset.addEventListener("click", () => runAction("/api/demo/reset", "Demo đã trở về trạng thái ban đầu."));

request("/api/demo/state").catch(() => {});
