import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import { ACTIVE_ASSESSMENT_KEY, SESSION_KEY } from './lib/session';
import { go } from './lib/navigation';

localStorage.removeItem('career-compass-session');

document.addEventListener('click', (event) => {
  const button = event.target.closest?.('.reset-link');
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  if (window.confirm('Bạn có chắc muốn xóa toàn bộ khảo sát, hồ sơ và lộ trình?')) {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(ACTIVE_ASSESSMENT_KEY);
    localStorage.removeItem('cc-done');
    go('/');
  }
}, true);

createRoot(document.getElementById('root')).render(<App />);
