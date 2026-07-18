const API_ROOT = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function post(path, body = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    const error = payload.error || {};
    throw new Error(`${error.code || 'request_failed'}: ${error.message || 'Không thể hoàn tất yêu cầu.'}`);
  }
  return payload;
}

export const companionApi = {
  analyze: () => post('/api/companion/analyze', { student_id: 'stu_uet_0001', profile_version: 1, fixture_selector: 'initial' }),
  plan: analysisId => post('/api/companion/plan', { analysis_id: analysisId }),
  followup: analysisId => post('/api/companion/followup', { baseline_analysis_id: analysisId, student_id: 'stu_uet_0001', profile_version: 2, fixture_selector: 'week3' }),
  expandPlan: (planId, taskId) => post('/api/companion/content/expand-plan', { plan_id: planId, task_id: taskId, max_steps: 4 }),
  reassessment: (planId, skillId) => post('/api/companion/content/reassessment', { plan_id: planId, target_skill_id: skillId, question_count: 3, max_score: 10 }),
  feedback: question => post('/api/companion/content/feedback', {
    student_id: 'stu_uet_0001', question_id: question.question_id, skill_id: question.skill_id,
    question_prompt: question.prompt, student_answer: question.options?.find(item => item !== question.correct_answer) || 'Câu trả lời chưa đúng',
    expected_answer: question.correct_answer, is_correct: false, detected_error_type: 'cách áp dụng quy tắc',
  }),
  reset: () => post('/api/companion/reset'),
};
