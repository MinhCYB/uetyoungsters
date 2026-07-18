import React from 'react';
import { HeaderAI } from '../components/common';
import { readSession } from '../lib/session';
import { go } from '../lib/navigation';

export function RoadmapAI({id}){const session=readSession();const roadmap=session.aiAnalysis?.roadmaps?.find(r=>r.targetCareer?.id===id)||null;return <><HeaderAI page="roadmap"/><main className="page">{roadmap?<div><div className="eyebrow">Lộ trình do AI tạo</div><h1>{roadmap.title}</h1></div>:<div className="analysis-empty"><div className="empty-orbit"><span>AI</span></div><h1>Chưa có lộ trình</h1><p>Dữ liệu roadmap đang là <b>null</b>. Lộ trình chỉ xuất hiện sau khi người dùng chọn một nghề trong kết quả AI.</p><button className="ghost" onClick={()=>go('/careers')}>Quay lại nghề gợi ý</button></div>}</main></>}
