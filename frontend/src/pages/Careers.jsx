import React, { useEffect, useMemo, useState } from 'react';
import { EmptyData, HeaderAI, Pill } from '../components/common';
import { readSession, saveSession } from '../lib/session';
import { go } from '../lib/navigation';

const CAREER_GROUPS = [
  { id: 'current_fit', label: 'Phù hợp với hiện tại', description: 'Có nhiều điểm tương thích với sở thích, kỹ năng và điều kiện hiện tại.' },
  { id: 'growth', label: 'Có thể phát triển', description: 'Có nền tảng phù hợp và cần bổ sung một số kỹ năng để tiến gần hơn.' },
  { id: 'explore', label: 'Đáng để khám phá', description: 'Hướng mở rộng giúp bạn kiểm tra thêm những khả năng chưa thể hiện đầy đủ.' },
];

function roadmapRequirements(session) {
  const basic = session.answers?.basic || {};
  const type = basic.profileType;
  const missing = [];
  if (!type) return ['Đối tượng hồ sơ'];
  if (!basic.age) missing.push('Tuổi');
  if (!basic.region) missing.push('Khu vực hiện tại');
  if (type === 'student') {
    if (!basic.school) missing.push('Trường THPT');
    if (!basic.grade) missing.push('Lớp');
    if (!basic.schoolYear) missing.push('Năm học');
  }
  if (type === 'university') {
    if (!basic.school) missing.push('Trường đại học');
    if (!basic.major) missing.push('Ngành học');
    if (!basic.studyYear) missing.push('Sinh viên năm');
    if (!basic.cvName) missing.push('CV');
  }
  if (type === 'professional') {
    if (!basic.currentJob) missing.push('Công việc hiện tại');
    if (basic.experienceYears === '' || basic.experienceYears == null) missing.push('Số năm kinh nghiệm');
    if (!basic.cvName) missing.push('CV');
  }
  return missing;
}

function CareerCard({ career, rank, skills, expanded, source, onToggle, onRoadmap }) {
  const gaps = career.skillGaps || [];
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  useEffect(() => {
    if (!expanded || detail) return undefined;
    const controller = new AbortController();
    const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
    setDetailLoading(true);
    fetch(`${base}/careers/${encodeURIComponent(career.id)}`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
      .then(payload => { setDetail(payload); setDetailError(''); })
      .catch(error => { if (error.name !== 'AbortError') setDetailError('Chưa có dữ liệu chi tiết đã được kiểm chứng cho nghề này.'); })
      .finally(() => setDetailLoading(false));
    return () => controller.abort();
  }, [expanded, career.id, detail]);
  return <article className="career-result-card">
    <div className="career-result-rank"><small>{source === 'ai' ? 'AI gợi ý' : 'Tự chọn'}</small><b>{String(rank).padStart(2, '0')}</b></div>
    <div className="career-result-main">
      <div className="career-result-head"><div><div className="career-source"><Pill tone={source === 'ai' ? 'success' : 'outline'}>{source === 'ai' ? 'Kết quả AI' : 'Danh mục nghề'}</Pill></div><h3>{career.title}</h3><p>{career.reason || 'Nghề được chọn từ danh mục để bạn chủ động khám phá và tạo lộ trình.'}</p></div>{source === 'ai' && <div className="career-match-score"><b>{career.matchScore ?? '—'}</b><span>{career.matchScore != null ? '/100' : 'Chưa chấm'}</span></div>}</div>
      {expanded && <div className="career-expanded">
        <div><h4>Công việc thường làm</h4>{detailLoading && <p>Đang tải dữ liệu nghề…</p>}{detailError && <p>{detailError}</p>}{detail && <>{detail.typical_tasks?.length ? <ul>{detail.typical_tasks.slice(0, 8).map((item, index) => <li key={`${item.evidence_id || 'task'}-${index}`}>{item.text_vi || item.text || item}{item.source_name && <small> · {item.source_name}</small>}</li>)}</ul> : <p>Chưa trích xuất được nhiệm vụ cụ thể từ các nguồn hiện có.</p>}<small>{detail.posting_count} tin tuyển dụng · {detail.company_count} doanh nghiệp · {detail.evidence_count} nguồn bằng chứng</small>{detail.work_modes?.length > 0 && <p>Hình thức: {detail.work_modes.join(', ')}</p>}{detail.sources?.length > 0 && <p>Nguồn: {detail.sources.filter(item => item.source_url).slice(0, 3).map((item, index) => <React.Fragment key={item.evidence_id}>{index > 0 ? ', ' : ''}<a href={item.source_url} target="_blank" rel="noreferrer">{item.source_name || item.title}</a></React.Fragment>)}</p>}</>}</div>
        <div><h4>Kỹ năng đang có</h4>{skills.length ? <div className="pills">{skills.map(item => <Pill key={item.name}>{item.name}</Pill>)}</div> : <p>Chưa có kỹ năng được xác nhận trong hồ sơ.</p>}</div>
        <div><h4>Kỹ năng thị trường yêu cầu</h4>{detail?.top_skills?.length ? <ul>{detail.top_skills.slice(0, 10).map(item => <li key={item.skill_id}>{item.skill_name}{item.source_type === 'job_posting' ? ` (${Math.round((item.share_of_career_jobs || 0) * 100)}% tin tuyển dụng)` : item.source_type === 'onet_software' ? ` (${item.in_demand ? 'đang được tuyển dụng yêu cầu' : 'công nghệ phổ biến'})` : item.importance_score != null ? ` (độ quan trọng ${item.importance_score.toFixed(1)}/5)` : ''}</li>)}</ul> : gaps.length ? <ul>{gaps.map(item => <li key={item}>{item}</li>)}</ul> : <p>Chưa có đủ dữ liệu kỹ năng cho nghề này.</p>}</div>
      </div>}
      <div className="career-result-actions"><button className="ghost" onClick={onToggle}>{expanded ? 'Thu gọn' : 'Xem chi tiết'}</button><button className="primary" onClick={onRoadmap}>Lộ trình <span>→</span></button></div>
    </div>
  </article>;
}

export function CareersAISchema() {
  const session = readSession();
  const aiResults = session.aiAnalysis?.careers || [];
  const skills = session.answers?.skills || [];
  const [query, setQuery] = useState('');
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchError, setSearchError] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [requirementNotice, setRequirementNotice] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
      fetch(`${base}/careers/search?q=${encodeURIComponent(query)}&limit=40`, { signal: controller.signal })
        .then(async response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
        .then(data => { setCatalog(data.items || []); setSearchError(''); })
        .catch(error => { if (error.name !== 'AbortError') setSearchError('Chưa thể tải danh mục nghề từ backend.'); })
        .finally(() => setLoading(false));
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query]);

  const aiIds = useMemo(() => new Set(aiResults.map(item => item.id)), [aiResults]);
  const userResults = catalog.filter(item => !aiIds.has(item.id));
  const primary = aiResults.slice(0, 5).map((career, index) => ({ ...career, group: career.group || ['current_fit', 'current_fit', 'growth', 'growth', 'explore'][index] }));
  const openRoadmap = career => {
    const missing = roadmapRequirements(session);
    if (missing.length) {
      setRequirementNotice({ career, missing });
      return;
    }
    saveSession({ selectedCareerId: career.id, selectedCareer: { id: career.id, title: career.title, source: aiIds.has(career.id) ? 'ai' : 'user' } });
    go(`/roadmap/${career.id}`);
  };

  return <><HeaderAI page="careers"/><main className="page careers-schema">
    <div className="page-intro careers-intro"><div><button className="back" onClick={() => go('/profile')}>← Hồ sơ của tôi</button><div className="eyebrow">Khám phá nghề nghiệp</div><h1>Tìm một hướng nghề bạn muốn khám phá</h1><p>Bạn luôn có thể tự tìm nghề. Khi AI có kết quả, các gợi ý cá nhân hóa sẽ xuất hiện riêng bên dưới.</p></div><div className="career-count"><b>{aiResults.length}</b><span>gợi ý từ AI</span></div></div>
    <section className="career-search-section"><label htmlFor="career-search">Tìm kiếm nghề</label><div className="career-search-box"><span>⌕</span><input id="career-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Ví dụ: phân tích dữ liệu, marketing, kế toán..."/><small>{loading ? 'Đang tải…' : `${userResults.length} kết quả`}</small></div>{searchError && <div className="notice warning">{searchError}</div>}
      <div className="career-result-list user-career-results">{userResults.map((career, index) => <CareerCard key={career.id} career={career} rank={index + 1} skills={skills} source="user" expanded={expandedId === career.id} onToggle={() => setExpandedId(expandedId === career.id ? null : career.id)} onRoadmap={() => openRoadmap(career)}/>)}</div>
      {!loading && !searchError && !userResults.length && <EmptyData text="Không tìm thấy nghề phù hợp với từ khóa này."/>}
    </section>

    <section className="ai-career-section"><div className="career-group-title"><div><span>AI</span><div><h2>Nghề được AI gợi ý</h2><p>Khu vực này tự động cập nhật sau khi hệ thống hoàn tất phân tích hồ sơ và bài đánh giá.</p></div></div><Pill tone={aiResults.length ? 'success' : 'outline'}>{aiResults.length} nghề</Pill></div>
      {aiResults.length ? <div className="career-group-list">{CAREER_GROUPS.map(group => { const careers = primary.filter(item => item.group === group.id); return <section className="career-group" key={group.id}><div className="career-group-title"><div><span>{group.id === 'current_fit' ? '01' : group.id === 'growth' ? '02' : '03'}</span><div><h2>{group.label}</h2><p>{group.description}</p></div></div></div><div className="career-result-list">{careers.map(career => <CareerCard key={career.id} career={career} rank={primary.findIndex(item => item.id === career.id) + 1} skills={skills} source="ai" expanded={expandedId === career.id} onToggle={() => setExpandedId(expandedId === career.id ? null : career.id)} onRoadmap={() => openRoadmap(career)}/>)}</div></section>; })}</div> : <div className="ai-career-empty"><div className="empty-orbit"><span>AI</span></div><div><h3>Chưa có gợi ý cá nhân hóa</h3><p>Bạn vẫn có thể tìm nghề và tạo lộ trình ở phía trên mà không cần chờ AI.</p><button className="ghost" onClick={() => go('/assessment')}>Làm bài đánh giá</button></div></div>}
    </section>

    {requirementNotice && <div className="career-requirement-backdrop" role="presentation" onClick={() => setRequirementNotice(null)}><section className="career-requirement-modal" role="dialog" aria-modal="true" aria-labelledby="requirement-title" onClick={event => event.stopPropagation()}><Pill tone="warning">Cần bổ sung hồ sơ</Pill><h2 id="requirement-title">Chưa thể tạo lộ trình {requirementNotice.career.title}</h2><p>Hãy bổ sung các thông tin sau để lộ trình phù hợp với điều kiện thực tế:</p><ul>{requirementNotice.missing.map(item => <li key={item}>{item}</li>)}</ul><div><button className="ghost" onClick={() => setRequirementNotice(null)}>Để sau</button><button className="primary" onClick={() => go('/profile')}>Cập nhật hồ sơ <span>→</span></button></div></section></div>}
  </main></>;
}
