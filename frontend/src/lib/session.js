export const SESSION_KEY = 'career-compass-session-v3';
export const ACTIVE_ASSESSMENT_KEY = 'career-compass-active-assessment-v3';
const initialSession = {
  displayName: null,
  assessmentCompleted: false,
  profileStatus: 'draft',
  selectedCareerId: null,
  answers: null,
  aiAnalysis: null,
  abilityAdjustments: null,
  abilityReviewed: false,
};
export const readSession = () => {
  try { return { ...initialSession, ...JSON.parse(localStorage.getItem(SESSION_KEY) || '{}') }; }
  catch { return initialSession; }
};
export const saveSession = (patch) => {
  const next = { ...readSession(), ...patch };
  localStorage.setItem(SESSION_KEY, JSON.stringify(next));
  window.dispatchEvent(new Event('career-session-change'));
  return next;
};
export const readActiveAssessment=()=>{try{return JSON.parse(localStorage.getItem(ACTIVE_ASSESSMENT_KEY)||'null')}catch{return null}};
