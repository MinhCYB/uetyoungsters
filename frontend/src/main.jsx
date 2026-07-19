import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import { ACTIVE_ASSESSMENT_KEY, SESSION_KEY, readActiveAssessment, readSession } from './lib/session';
import { go } from './lib/navigation';
import { api } from './lib/api';

localStorage.removeItem('career-compass-session');

document.addEventListener('click', async (event) => {
  const button = event.target.closest?.('.reset-link');
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  if (window.confirm('Bạn có chắc muốn xóa toàn bộ khảo sát, hồ sơ và lộ trình?')) {
    const assessmentId = readActiveAssessment()?.payload?.assessment_id || readSession()?.answers?.assessmentId;
    if (assessmentId) {
      try {
        await api(`/api/assessment/${encodeURIComponent(assessmentId)}`, { method: 'DELETE' });
      } catch (error) {
        if (error.status !== 404) {
          window.alert(`Chưa thể xóa khảo sát trên máy chủ: ${error.message}`);
          return;
        }
      }
    }
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(ACTIVE_ASSESSMENT_KEY);
    localStorage.removeItem('cc-done');
    go('/');
  }
}, true);

createRoot(document.getElementById('root')).render(<App />);
