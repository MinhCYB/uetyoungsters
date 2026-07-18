import React, { useEffect, useState } from 'react';
import { AssessmentPersistent } from './pages/Assessment';
import { CandidateProfile } from './pages/Profile';
import { AbilitiesSchema } from './pages/Abilities';
import { CareersAISchema } from './pages/Careers';
import { RoadmapAI } from './pages/Roadmap';
import { Home, Locked } from './components/common';
import { AcceptInvitation, ForgotPassword, Login, ProfessionalRegister } from './pages/Auth';
import { Dashboard } from './pages/Dashboard';
import { restoreAuth } from './lib/api';
import {
  readSession,
} from './lib/session';

export default function App() {
  const [path, setPath] = useState(location.pathname);
  const [authUser, setAuthUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    const handleNavigation = () => {
      setPath(location.pathname);
    };
    addEventListener('popstate', handleNavigation);
    return () => removeEventListener('popstate', handleNavigation);
  }, []);

  useEffect(() => {
    restoreAuth().then(user => { setAuthUser(user); setAuthReady(true); });
    const sync = event => setAuthUser(event.detail);
    addEventListener('auth-session-change', sync);
    return () => removeEventListener('auth-session-change', sync);
  }, []);

  if (path === '/login') return <Login onAuthenticated={setAuthUser}/>;
  if (path === '/register/professional') return <ProfessionalRegister onAuthenticated={setAuthUser}/>;
  if (path === '/accept-invitation') return <AcceptInvitation onAuthenticated={setAuthUser}/>;
  if (path === '/forgot-password') return <ForgotPassword/>;
  if (path === '/dashboard') {
    if (!authReady) return <main className="page backend-state"><div className="loading-ring"/><h1>Đang xác thực phiên</h1></main>;
    return authUser ? <Dashboard user={authUser} onLogout={()=>setAuthUser(null)}/> : <Login onAuthenticated={setAuthUser}/>;
  }

  const session = readSession();
  const unlocked = session.assessmentCompleted && session.profileStatus === 'confirmed';
  if (path.startsWith('/assessment')) return <AssessmentPersistent />;
  if (path === '/profile') return <CandidateProfile />;
  if (path === '/abilities') return session.assessmentCompleted ? <AbilitiesSchema /> : <Locked type="abilities" />;
  if (path === '/careers') return unlocked ? <CareersAISchema /> : <Locked />;
  if (path.startsWith('/roadmap')) {
    const id = path.split('/')[2];
    return unlocked && session.selectedCareerId ? <RoadmapAI id={id} /> : <Locked type="roadmap" />;
  }
  return <Home />;
}
