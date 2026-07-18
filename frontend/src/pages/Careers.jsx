import React, { useState } from 'react';
import { EmptyData, HeaderAI, Pill } from '../components/common';
import { readSession, saveSession } from '../lib/session';
import { go } from '../lib/navigation';

const CAREER_GROUPS=[
  {id:'current_fit',label:'Phù hợp với hiện tại',description:'Có nhiều điểm tương thích với sở thích, kỹ năng và điều kiện hiện tại.'},
  {id:'growth',label:'Có thể phát triển',description:'Có nền tảng phù hợp và cần bổ sung một số kỹ năng để tiến gần hơn.'},
  {id:'explore',label:'Đáng để khám phá',description:'Hướng đi mở rộng giúp bạn kiểm tra thêm những khả năng chưa thể hiện đầy đủ.'},
];

function CareerResultCard({career,rank,skills,expanded,onToggle}){
  const gaps=career.skillGaps||[];
  return <article className="career-result-card"><div className="career-result-rank"><small>Gợi ý</small><b>{String(rank).padStart(2,'0')}</b></div><div className="career-result-main"><div className="career-result-head"><div><h3>{career.title}</h3><p>{career.reason||'Chưa có phần giải thích từ hệ thống phân tích.'}</p></div><div className="career-match-score"><b>{career.matchScore??'—'}</b><span>{career.matchScore!=null?'/100':'Chưa chấm'}</span></div></div>{expanded&&<div className="career-expanded"><div><h4>Thế mạnh và kỹ năng đang có</h4>{skills.length?<div className="pills">{skills.map(item=><Pill key={item.name}>{item.name}</Pill>)}</div>:<p>Chưa có kỹ năng nào được xác nhận trong hồ sơ.</p>}</div><div><h4>Kỹ năng cần bổ sung</h4>{gaps.length?<ul>{gaps.map(item=><li key={item}>{item}</li>)}</ul>:<p>Chưa có dữ liệu khoảng cách kỹ năng.</p>}</div><div className="career-market-empty"><small>Nhu cầu tuyển dụng tại khu vực</small><b>Chưa kết nối dữ liệu thị trường</b><span>Backend nghề nghiệp sẽ cập nhật phần này sau.</span></div></div>}<div className="career-result-actions"><button className="ghost" onClick={onToggle}>{expanded?'Thu gọn':'Xem chi tiết'}</button><button className="primary" onClick={()=>{saveSession({selectedCareerId:career.id});go('/roadmap/'+career.id)}}>Chọn nghề này <span>→</span></button></div></div></article>
}

export function CareersAISchema(){
  const session=readSession();
  const results=session.aiAnalysis?.careers||[];
  const skills=session.answers?.skills||[];
  const [expandedId,setExpandedId]=useState(null);
  const [showMore,setShowMore]=useState(false);
  const primary=results.slice(0,5).map((career,index)=>({...career,group:career.group||(['current_fit','current_fit','growth','growth','explore'][index])}));
  const additional=results.slice(5);
  return <><HeaderAI page="careers"/><main className="page careers-schema"><div className="page-intro careers-intro"><div><button className="back" onClick={()=>go('/profile')}>← Hồ sơ của tôi</button><div className="eyebrow">Kết quả phân tích hướng nghiệp</div><h1>Những hướng nghề đáng cân nhắc</h1><p>Kết quả được chia theo mức độ sẵn sàng, không phải kết luận cố định. Bạn có thể quay lại cập nhật hồ sơ bất cứ lúc nào.</p></div><div className="career-count"><b>{results.length}</b><span>nghề đang có dữ liệu</span></div></div>
  {results.length? <div className="career-group-list">{CAREER_GROUPS.map(group=>{const careers=primary.filter(item=>item.group===group.id);return <section className="career-group" key={group.id}><div className="career-group-title"><div><span>{group.id==='current_fit'?'01':group.id==='growth'?'02':'03'}</span><div><h2>{group.label}</h2><p>{group.description}</p></div></div><Pill tone={careers.length?'soft':'outline'}>{careers.length} nghề</Pill></div>{careers.length?<div className="career-result-list">{careers.map(career=><CareerResultCard key={career.id} career={career} rank={primary.findIndex(item=>item.id===career.id)+1} skills={skills} expanded={expandedId===career.id} onToggle={()=>setExpandedId(expandedId===career.id?null:career.id)}/>)}</div>:<div className="career-group-empty"><span>Chưa có nghề trong nhóm này</span><p>AI chưa trả về đủ dữ liệu phù hợp để đưa ra gợi ý.</p></div>}</section>})}
  <section className="additional-careers"><div><h2>Gợi ý thêm</h2><p>Các hướng phụ ngoài năm nghề chính sẽ xuất hiện tại đây.</p></div><button className="ghost" onClick={()=>setShowMore(!showMore)}>{showMore?'Ẩn gợi ý thêm':'Xem thêm nghề'}</button>{showMore&&<div className="additional-content">{additional.length?additional.map((career,index)=><CareerResultCard key={career.id} career={career} rank={index+6} skills={skills} expanded={expandedId===career.id} onToggle={()=>setExpandedId(expandedId===career.id?null:career.id)}/>):<EmptyData text="Chưa có nghề gợi ý thêm. Khu vực này sẽ được điền khi AI trả về nhiều hơn năm nghề."/>}</div>}</section></div>
  :<div className="analysis-empty"><div className="empty-orbit"><span>AI</span></div><h2>Chưa có nghề gợi ý</h2><p>Danh sách nghề chỉ xuất hiện sau khi hồ sơ được phân tích và xác nhận.</p><button className="ghost" onClick={()=>go('/profile')}>Quay lại kiểm tra hồ sơ</button></div>}</main></>
}

function CareersAI(){const session=readSession();const results=session.aiAnalysis?.careers||null;return <><HeaderAI page="careers"/><main className="page careers"><div className="page-intro"><div><button className="back" onClick={()=>go('/profile')}>← Hồ sơ của tôi</button><div className="eyebrow">Kết quả phân tích</div><h1>Nghề phù hợp với bạn</h1><p>Danh sách này không có dữ liệu cài sẵn và chỉ xuất hiện từ phản hồi AI.</p></div></div>{results?.length?results.map(c=><section key={c.id} className="career-card"><div className="career-main"><h2>{c.title}</h2><p>{c.reason}</p><button className="primary" onClick={()=>{saveSession({selectedCareerId:c.id});go('/roadmap/'+c.id)}}>Chọn nghề này</button></div></section>):<div className="analysis-empty"><div className="empty-orbit"><span>AI</span></div><h2>Chưa có nghề gợi ý</h2><p>`aiAnalysis.careers` hiện đang là <b>null</b>. Sau này API AI sẽ điền kết quả dựa trên câu trả lời đã xác nhận của người dùng.</p><button className="ghost" onClick={()=>go('/profile')}>Quay lại kiểm tra hồ sơ</button></div>}</main></>}
