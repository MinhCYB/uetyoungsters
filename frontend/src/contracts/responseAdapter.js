const required = (value, path) => {
  if (value === undefined || value === null || value === '') throw new Error(`Thiếu field bắt buộc: ${path}`);
  return value;
};

const displayEntity = (item, path) => ({
  id: required(item.id, `${path}.id`),
  displayName: required(item.display_name, `${path}.display_name`),
});

export function adaptAnalysisResponse(response) {
  if (response.contract_version !== '1.0.0') throw new Error(`Không hỗ trợ contract ${response.contract_version}`);
  const kind = required(response.response_type, 'response_type');
  const common = {
    kind,
    requestId: required(response.request_id, 'request_id'),
    studentId: required(response.student_id, 'student_id'),
    displayName: response.display_name || 'Nguyễn Minh Anh',
    generatedAt: required(response.generated_at, 'generated_at'),
    title: required(response.title, 'title'),
    summary: response.summary || null,
    warnings: (response.warnings || []).map((warning, index) => ({
      code: required(warning.code, `warnings[${index}].code`),
      severity: required(warning.severity, `warnings[${index}].severity`),
      title: required(warning.title, `warnings[${index}].title`),
      message: required(warning.message, `warnings[${index}].message`),
      action: warning.suggested_action || null,
    })),
    nextSteps: (response.next_steps || []).map((step, index) => ({
      id: required(step.step_id, `next_steps[${index}].step_id`),
      title: required(step.title, `next_steps[${index}].title`),
      description: step.description || null,
      priority: required(step.priority, `next_steps[${index}].priority`),
      route: step.route || null,
    })),
  };

  if (kind === 'initial_analysis') return {
    ...common,
    analysisId: response.analysis_id || null,
    profileVersion: response.profile_version || null,
    marketMessage: response.market_message || null,
    abilities: required(response.ability_profile, 'ability_profile').map((ability, index) => ({
      ...displayEntity({ id: ability.ability_id, display_name: ability.display_name }, `ability_profile[${index}]`),
      level: required(ability.level, `ability_profile[${index}].level`),
      score: ability.score ?? null,
      maxScore: ability.max_score ?? null,
      confidence: ability.confidence ?? null,
      explanation: ability.explanation || null,
    })),
    gaps: required(response.gaps, 'gaps').map((gap, index) => ({
      id: required(gap.gap_id, `gaps[${index}].gap_id`),
      type: required(gap.gap_type, `gaps[${index}].gap_type`),
      dimension: gap.gap_dimension ?? null,
      subject: displayEntity({ id: gap.subject_id, display_name: gap.display_name }, `gaps[${index}]`),
      priority: required(gap.priority, `gaps[${index}].priority`),
      description: required(gap.description, `gaps[${index}].description`),
      status: gap.status || 'open',
    })),
  };

  if (kind === 'plan_generation') return {
    ...common,
    planId: required(response.plan_id, 'plan_id'),
    durationWeeks: required(response.duration_weeks, 'duration_weeks'),
    progressPercentage: required(response.progress_percentage, 'progress_percentage'),
    weeks: required(response.weekly_plan, 'weekly_plan').map((week, index) => ({
      weekNumber: required(week.week_number, `weekly_plan[${index}].week_number`),
      title: required(week.title, `weekly_plan[${index}].title`),
      objective: required(week.objective, `weekly_plan[${index}].objective`),
      estimatedMinutes: required(week.estimated_minutes, `weekly_plan[${index}].estimated_minutes`),
      activities: (week.activities || []).map(activity => ({ id: activity.activity_id, title: activity.title, status: activity.status, taskType: activity.task_type || null, skillId: activity.skill_id || null, careerGroupId: activity.career_group_id || null, estimatedMinutes: activity.estimated_minutes || null })),
    })),
    estimatedMinutes: response.estimated_minutes ?? null,
    activities: (response.activities || []).map(activity => ({ id: activity.activity_id, title: activity.title, status: activity.status, taskType: activity.task_type || null, skillId: activity.skill_id || null, careerGroupId: activity.career_group_id || null, estimatedMinutes: activity.estimated_minutes || null })),
  };

  if (kind === 'followup_evaluation') return {
    ...common,
    baselineAnalysisId: required(response.baseline_analysis_id, 'baseline_analysis_id'),
    progressPercentage: required(response.progress_percentage, 'progress_percentage'),
    comparisons: required(response.before_after, 'before_after').map((item, index) => ({
      subject: displayEntity({ id: item.subject_id, display_name: item.display_name }, `before_after[${index}]`),
      before: required(item.before, `before_after[${index}].before`),
      after: required(item.after, `before_after[${index}].after`),
      maxValue: required(item.max_value, `before_after[${index}].max_value`),
      delta: required(item.delta, `before_after[${index}].delta`),
      interpretation: item.interpretation || null,
    })),
    outcomes: response.outcomes || [],
    updatedGaps: response.updated_gaps || [],
  };
  throw new Error(`response_type không được hỗ trợ: ${kind}`);
}
