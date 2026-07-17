from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.pipeline import preprocess_jobs, build_market_signals
from src.recommender import load_career_profiles, recommend_careers


st.set_page_config(page_title="Career Intelligence Baseline", layout="wide")
st.title("Career Intelligence Baseline")
st.caption(
    "AI không chọn nghề thay bạn. Hệ thống đưa ra các hướng để khám phá dựa trên "
    "bằng chứng năng lực, sở thích và tín hiệu thị trường."
)

jobs = preprocess_jobs(
    ROOT / "data" / "raw" / "jobs.csv",
    ROOT / "data" / "skill_taxonomy.json",
)
careers = load_career_profiles(ROOT / "data" / "career_profiles.json")

with st.sidebar:
    st.header("Hồ sơ ban đầu")
    location = st.selectbox(
        "Khu vực quan tâm",
        ["Hà Nội", "TP.HCM", "Bắc Ninh", "Đà Nẵng", "Không ưu tiên"],
    )
    skills = st.multiselect(
        "Kỹ năng đã có",
        [
            "sql", "excel", "power bi", "python", "analytics",
            "testing", "communication", "customer research",
            "forecasting", "plc", "industrial electricity"
        ],
    )
    interests_text = st.text_area(
        "Bạn thích làm những hoạt động nào?",
        "Tôi thích phân tích số liệu, tìm quy luật và làm việc với máy tính.",
    )

tab1, tab2 = st.tabs(["Gợi ý nghề nghiệp", "Tín hiệu thị trường"])

with tab1:
    if st.button("Tạo gợi ý baseline", type="primary"):
        profile = {
            "location": None if location == "Không ưu tiên" else location,
            "skills": skills,
            "interests": [interests_text],
        }
        recommendations = recommend_careers(profile, careers, jobs, top_k=5)

        for index, item in enumerate(recommendations, start=1):
            with st.expander(
                f"{index}. {item['career']} — điểm tham khảo {item['score']}",
                expanded=index <= 3,
            ):
                st.write(f"**Độ không chắc chắn:** {item['uncertainty']}")
                for reason in item["explanation"]:
                    st.write(f"- {reason}")
                st.write("**Lộ trình tham khảo:**")
                for step_no, step in enumerate(item["route"], start=1):
                    st.write(f"{step_no}. {step}")

        st.info(
            "Các điểm số chỉ dùng để xếp hạng hướng khám phá, không phải kết luận "
            "về năng lực hay tương lai nghề nghiệp."
        )

with tab2:
    signals = build_market_signals(jobs)
    st.dataframe(signals, use_container_width=True)
    st.caption(
        "Dữ liệu hiện là mẫu nhỏ. Baseline thật cần dữ liệu lớn hơn, chống trùng "
        "tin tuyển dụng và đánh giá độ chính xác trích xuất kỹ năng."
    )
