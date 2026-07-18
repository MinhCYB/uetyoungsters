export const RESPONSE_KIND_LABELS = {
  initial_analysis: 'Phân tích ban đầu',
  plan_generation: 'Kế hoạch phát triển',
  followup_evaluation: 'Đánh giá tiến triển',
};

export const ABILITY_LEVEL_LABELS = {
  not_observed: 'Chưa đủ dữ liệu',
  emerging: 'Đang hình thành',
  developing: 'Đang phát triển',
  proficient: 'Thành thạo',
  advanced: 'Nổi trội',
};

export const GAP_TYPE_LABELS = {
  knowledge: 'Kiến thức',
  skill: 'Kỹ năng thực hành',
  experience: 'Trải nghiệm',
};

export const PRIORITY_LABELS = {
  low: 'Thấp',
  medium: 'Trung bình',
  high: 'Cao',
  critical: 'Cần ưu tiên ngay',
};

export const WARNING_SEVERITY_LABELS = {
  info: 'Lưu ý',
  caution: 'Cần thận trọng',
  important: 'Quan trọng',
};

export const STEP_STATUS_LABELS = {
  not_started: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  completed: 'Đã hoàn thành',
  skipped: 'Đã bỏ qua',
};

export function enumLabel(dictionary, value) {
  return dictionary[value] || value || 'Chưa xác định';
}
