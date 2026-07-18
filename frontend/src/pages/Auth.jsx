import React, { useState } from 'react';
import { Logo } from '../components/common';
import { api, setAccessToken } from '../lib/api';
import { go } from '../lib/navigation';

function AuthShell({ eyebrow, title, description, children }) {
  return <main className="auth-page"><section className="auth-aside"><Logo/><div><span className="auth-kicker">Career Compass Account</span><h2>Một tài khoản.<br/>Đúng phạm vi.<br/>Đúng trách nhiệm.</h2><p>Tài khoản trường được cấp từ cấp quản lý; người đi làm có thể tự đăng ký.</p></div><small>RBAC · Tenant scope · Class scope · Ownership</small></section><section className="auth-panel"><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p>{children}</section></main>;
}

function Field({ label, ...props }) {
  return <label className="auth-field"><span>{label}</span><input {...props}/></label>;
}

export function Login({ onAuthenticated }) {
  const [form,setForm]=useState({email:'',password:''}); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const submit=async e=>{e.preventDefault();setBusy(true);setError('');try{const data=await api('/api/auth/login',{method:'POST',body:JSON.stringify(form)},false);setAccessToken(data.accessToken);onAuthenticated(data.user);go('/dashboard')}catch(reason){setError(reason.message)}finally{setBusy(false)}};
  return <AuthShell eyebrow="Đăng nhập" title="Chào mừng bạn trở lại" description="Đăng nhập bằng tài khoản đã được cấp hoặc tài khoản Professional."><form className="auth-form" onSubmit={submit}><Field label="Email" type="email" required autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/><Field label="Mật khẩu" type="password" required autoComplete="current-password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>{error&&<div className="auth-error">{error}</div>}<button className="primary auth-submit" disabled={busy}>{busy?'Đang đăng nhập…':'Đăng nhập →'}</button></form><div className="auth-links"><button onClick={()=>go('/forgot-password')}>Quên mật khẩu?</button><button onClick={()=>go('/register/professional')}>Đăng ký cho người đi làm</button></div></AuthShell>;
}

export function ProfessionalRegister({ onAuthenticated }) {
  const [form,setForm]=useState({display_name:'',email:'',password:''}); const [error,setError]=useState('');
  const submit=async e=>{e.preventDefault();setError('');try{const data=await api('/api/auth/register/professional',{method:'POST',body:JSON.stringify(form)},false);setAccessToken(data.accessToken);onAuthenticated(data.user);go('/dashboard')}catch(reason){setError(reason.message)}};
  return <AuthShell eyebrow="Tài khoản cá nhân" title="Đăng ký Professional" description="Dành cho người đã đi làm, không thuộc trường. Vai trò được backend cố định là Professional."><form className="auth-form" onSubmit={submit}><Field label="Tên hiển thị" required value={form.display_name} onChange={e=>setForm({...form,display_name:e.target.value})}/><Field label="Email" type="email" required value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/><Field label="Mật khẩu (tối thiểu 8 ký tự)" type="password" minLength="8" required value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>{error&&<div className="auth-error">{error}</div>}<button className="primary auth-submit">Tạo tài khoản →</button></form><div className="auth-links"><button onClick={()=>go('/login')}>Đã có tài khoản? Đăng nhập</button></div></AuthShell>;
}

export function AcceptInvitation({ onAuthenticated }) {
  const token=new URLSearchParams(location.search).get('token')||''; const [password,setPassword]=useState(''); const [message,setMessage]=useState('');
  const submit=async e=>{e.preventDefault();try{const data=await api(`/api/auth/invitations/${encodeURIComponent(token)}/accept`,{method:'POST',body:JSON.stringify({password})},false);setAccessToken(data.accessToken);onAuthenticated(data.user);go('/dashboard')}catch(reason){setMessage(reason.message)}};
  return <AuthShell eyebrow="Lời mời tài khoản" title="Kích hoạt tài khoản" description="Đặt mật khẩu để hoàn tất tài khoản đã được nhà trường cấp."><form className="auth-form" onSubmit={submit}><Field label="Mật khẩu mới" type="password" minLength="8" required value={password} onChange={e=>setPassword(e.target.value)}/>{!token&&<div className="auth-error">Liên kết thiếu token lời mời.</div>}{message&&<div className="auth-error">{message}</div>}<button className="primary auth-submit" disabled={!token}>Kích hoạt tài khoản →</button></form></AuthShell>;
}

export function ForgotPassword() {
  const [email,setEmail]=useState(''); const [sent,setSent]=useState(false);
  const submit=async e=>{e.preventDefault();await api('/api/auth/forgot-password',{method:'POST',body:JSON.stringify({email})},false).catch(()=>null);setSent(true)};
  return <AuthShell eyebrow="Khôi phục truy cập" title="Quên mật khẩu" description="Phản hồi luôn giống nhau để không tiết lộ email có tồn tại trong hệ thống.">{sent?<div className="auth-success">Nếu email tồn tại, hướng dẫn đặt lại mật khẩu sẽ được gửi.</div>:<form className="auth-form" onSubmit={submit}><Field label="Email" type="email" required value={email} onChange={e=>setEmail(e.target.value)}/><button className="primary auth-submit">Gửi hướng dẫn →</button></form>}<div className="auth-links"><button onClick={()=>go('/login')}>Quay lại đăng nhập</button></div></AuthShell>;
}
