import React from 'react';
import { HeaderAI, Pill } from '../components/common';
import { readSession } from '../lib/session';
import { go } from '../lib/navigation';

export function RoadmapAI({ id }) {
  const session = readSession();
  const selectedCareer = session.selectedCareer?.id === id ? session.selectedCareer : null;
  const roadmap = session.aiAnalysis?.roadmaps?.find(item => item.targetCareer?.id === id) || null;
  const careerTitle = roadmap?.targetCareer?.title || selectedCareer?.title || 'nghề đã chọn';
  return <><HeaderAI page="roadmap"/><main className="page roadmap-entry">
    {roadmap ? <div><div className="eyebrow">Lộ trình do AI tạo</div><h1>{roadmap.title}</h1></div> : <div className="roadmap-pending"><Pill tone="soft">Nghề đã chọn</Pill><h1>Lộ trình {careerTitle}</h1><p>Bạn đã chọn nghề thành công. Nội dung chi tiết của lộ trình sẽ được tạo từ hồ sơ, CV (nếu cần), kết quả đánh giá và dữ liệu nghề nghiệp.</p><div className="roadmap-pending-grid"><article><span>01</span><h3>Kiểm tra dữ liệu đầu vào</h3><p>Hồ sơ đã đủ điều kiện cơ bản để bắt đầu tạo lộ trình.</p></article><article><span>02</span><h3>Phân tích khoảng cách</h3><p>Kỹ năng hiện tại và yêu cầu nghề sẽ được đối chiếu ở bước xử lý tiếp theo.</p></article><article><span>03</span><h3>Tạo kế hoạch theo tuần</h3><p>Thời gian, hoạt động và checkpoint sẽ xuất hiện khi backend trả kết quả.</p></article></div><div className="roadmap-pending-actions"><button className="ghost" onClick={() => go('/careers')}>← Chọn nghề khác</button><button className="primary" onClick={() => go('/assessment')}>Cập nhật bài đánh giá <span>→</span></button></div></div>}
  </main></>;
}
