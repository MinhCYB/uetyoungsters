// -- Active: 1778558687701@@127.0.0.1@5432
import React, { useCallback, useEffect, useRef, useState } from "react";
import { HeaderAI, Progress } from "../components/common";
import { readActiveAssessment, readSession, saveSession, ACTIVE_ASSESSMENT_KEY } from "../lib/session";
import { go } from "../lib/navigation";
import { api } from "../lib/api";
function wordCount(value) {
  return String(value || "").trim().split(/\s+/).filter(Boolean).length;
}
function meetsTextRequirement(question, value) {
  const text = String(value || "").trim();
  const words = wordCount(text);
  return words >= (question.min_words || 1) && text.length >= (question.min_chars || 1) && (!question.max_words || words <= question.max_words);
}
function QuestionInput({ question, value, setValue, toggleOption }) {
  const options = question.options || question.scale?.labels || [];
  if (["single_choice", "likert_5"].includes(question.type)) return <div className="backend-options">{options.map((option, i) => {
    const optionValue = typeof option === "object" ? option.value ?? option.id : question.type === "likert_5" ? i + (question.scale?.min || 1) : option;
    const label = typeof option === "object" ? option.label : option;
    return <button key={String(optionValue)} className={value === optionValue ? "chosen" : ""} onClick={() => setValue(optionValue)}><span>{label}</span></button>;
  })}</div>;
  if (question.type === "multi_choice") return <div className="backend-options">{options.map((option) => {
    const optionValue = typeof option === "object" ? option.value ?? option.id : option;
    const label = typeof option === "object" ? option.label : option;
    return <button key={String(optionValue)} className={value.includes(optionValue) ? "chosen" : ""} onClick={() => toggleOption(optionValue)}><span>{label}</span></button>;
  })}</div>;
  if (question.type === "number") return <div className="form-card"><label>Câu trả lời<input type="number" min={question.min} max={question.max} value={value} onChange={(event) => setValue(event.target.valueAsNumber)} /></label></div>;
  const valid = meetsTextRequirement(question, value);
  return <div className="form-card"><label className="wide">Câu trả lời<textarea value={value} placeholder={question.placeholder || "Nh\u1EADp c\xE2u tr\u1EA3 l\u1EDDi c\u1EE7a b\u1EA1n"} onChange={(event) => setValue(event.target.value)} /><small className={valid ? "text-limit valid" : "text-limit"}>{String(value || "").trim().length}/{question.min_chars || 2} ký tự tối thiểu{question.max_words ? ` \xB7 t\u1ED1i \u0111a ${question.max_words} t\u1EEB` : ""}</small></label></div>;
}
function QuestionInputV2(props) {
  const { question, value, setValue } = props;
  if (question.type === "ranking") {
    const selected = Array.isArray(value) ? value : [];
    const limit = question.required_count || 5;
    return <div className="ranking-list">{(question.items || []).map((item) => {
      const position = selected.indexOf(item.id);
      return <button key={item.id} className={position >= 0 ? "chosen" : ""} onClick={() => {
        if (position >= 0) setValue(selected.filter((id) => id !== item.id));
        else if (selected.length < limit) setValue([...selected, item.id]);
      }}><span>{position >= 0 ? position + 1 : "\u2014"}</span><b>{item.prompt}</b></button>;
    })}<small>Đã xếp hạng {selected.length}/{limit} giá trị</small></div>;
  }
  if (question.type === "point_allocation") {
    const allocation = value && typeof value === "object" && !Array.isArray(value) ? value : {};
    const total = Object.values(allocation).reduce((sum, n) => sum + (Number(n) || 0), 0);
    return <div className="allocation-list">{(question.options || []).map((option) => <label key={option}><span>{option}</span><input type="number" min="0" max="100" value={allocation[option] ?? ""} onChange={(e) => setValue({ ...allocation, [option]: Math.max(0, Number(e.target.value)) })} /></label>)}<div className={total === 100 ? "allocation-total valid" : "allocation-total"}><span>Tổng điểm</span><b>{total}/100</b></div></div>;
  }
  if (question.type === "tradeoff_group") {
    const answers = value && typeof value === "object" && !Array.isArray(value) ? value : {};
    return <div className="tradeoff-list">{(question.items || []).map((item) => {
      const answer = answers[item.id] || "";
      return <label key={item.id}><span>{item.prompt}</span><textarea value={answer} placeholder="Viết lựa chọn và lý do của bạn" onChange={(e) => setValue({ ...answers, [item.id]: e.target.value })} /><small>{String(answer).trim().length}/{question.min_chars_per_item || 2} ký tự tối thiểu</small></label>;
    })}</div>;
  }
  return <QuestionInput {...props} />;
}
function isQuestionVisible(question, responses) {
  const condition = question.display_if;
  if (!condition) return true;
  const answer = responses[condition.question_id];
  if (condition.operator === "equals") return answer === condition.value;
  if (condition.operator === "not_equals") return answer !== void 0 && answer !== "" && answer !== condition.value;
  if (condition.operator === "in") return condition.value.includes(answer);
  return true;
}
function AssessmentPersistent() {
  const cached = readActiveAssessment();
  const [payload, setPayload] = useState(cached?.payload || null);
  const [loading, setLoading] = useState(!cached?.payload);
  const [error, setError] = useState(null);
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [saveState, setSaveState] = useState("saved");
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const [index, setIndex] = useState(cached?.index || 0);
  const [responses, setResponses] = useState(cached?.responses || {});
  const configuredApiBase = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
  const apiBase = configuredApiBase.endsWith("/api") ? configuredApiBase : `${configuredApiBase}/api`;
  const responsesRef = useRef(cached?.responses || {});
  const dirtyQuestionIds = useRef(/* @__PURE__ */ new Set());
  const saveInFlight = useRef(false);
  const draftVersion = useRef(cached?.payload?.version || 1);
  const currentQuestionId = useRef(null);
  const metadataDirty = useRef(false);
  useEffect(() => {
    if (payload) return;
    const controller = new AbortController();
    api(`${apiBase}/assessment/questions?mode=standard_25_35_min`, { signal: controller.signal, headers: { Accept: "application/json" } }).then((data) => {
      if (!Array.isArray(data.questions)) throw new Error("Ph\u1EA3n h\u1ED3i kh\xF4ng c\xF3 tr\u01B0\u1EDDng questions d\u1EA1ng m\u1EA3ng");
      setPayload(data);
      setError(null);
    }).catch((reason) => {
      if (reason.name !== "AbortError") setError(reason.message);
    }).finally(() => setLoading(false));
    return () => controller.abort();
  }, [apiBase, payload]);
  useEffect(() => {
    if (payload) localStorage.setItem(ACTIVE_ASSESSMENT_KEY, JSON.stringify({ payload, responses, index }));
  }, [payload, responses, index]);
  useEffect(() => {
    responsesRef.current = responses;
  }, [responses]);
  useEffect(() => {
    if (payload?.version) draftVersion.current = payload.version;
  }, [payload?.version]);
  useEffect(() => {
    if (!payload?.assessment_id) return;
    let active = true;
    api(`${apiBase}/assessment/${payload.assessment_id}/draft`).then((draft) => {
      if (!active) return;
      draftVersion.current = draft.version || 1;
      setLastSavedAt(draft.last_saved_at || null);
      if (draft?.responses) setResponses((current) => {
        const localOnlyOrNewer = Object.keys(current).filter((id) => JSON.stringify(current[id]) !== JSON.stringify(draft.responses[id]));
        localOnlyOrNewer.forEach((id) => dirtyQuestionIds.current.add(id));
        if (localOnlyOrNewer.length) setSaveState(navigator.onLine ? "pending" : "offline");
        return { ...draft.responses, ...current };
      });
      if (cached?.index == null && draft.current_question_id) {
        const restoredIndex = payload.questions.findIndex((item) => item.id === draft.current_question_id);
        if (restoredIndex >= 0) setIndex(restoredIndex);
      }
    }).catch(() => null);
    return () => {
      active = false;
    };
  }, [apiBase, payload?.assessment_id]);
  const flushDraft = useCallback(async (keepalive = false) => {
    if (!payload?.assessment_id || saveInFlight.current || dirtyQuestionIds.current.size === 0 && !metadataDirty.current) return;
    const ids = [...dirtyQuestionIds.current];
    const changed = Object.fromEntries(ids.map((id) => [id, responsesRef.current[id]]));
    ids.forEach((id) => dirtyQuestionIds.current.delete(id));
    metadataDirty.current = false;
    saveInFlight.current = true;
    setSaveState("saving");
    try {
      const result = await api(`${apiBase}/assessment/${payload.assessment_id}/draft`, { method: "PATCH", keepalive, body: JSON.stringify({ question_set_id: payload.question_set_id, version: draftVersion.current, current_question_id: currentQuestionId.current, responses: changed }) });
      draftVersion.current = result.version;
      setLastSavedAt(result.saved_at || (/* @__PURE__ */ new Date()).toISOString());
      setSaveState("saved");
    } catch (reason) {
      ids.forEach((id) => dirtyQuestionIds.current.add(id));
      metadataDirty.current = true;
      if (reason.status === 409) {
        try {
          const draft = await api(`${apiBase}/assessment/${payload.assessment_id}/draft`);
          draftVersion.current = draft.version;
          setLastSavedAt(draft.last_saved_at || null);
          setSaveState("pending");
        } catch {
          setSaveState("error");
        }
      } else setSaveState(navigator.onLine ? "error" : "offline");
    } finally {
      saveInFlight.current = false;
    }
  }, [apiBase, payload?.assessment_id, payload?.question_set_id]);
  useEffect(() => {
    if (!payload?.assessment_id) return;
    const interval = setInterval(flushDraft, 1e4);
    const onVisibility = () => {
      if (document.visibilityState === "hidden") flushDraft();
    };
    const onOnline = () => flushDraft();
    const onPageHide = () => flushDraft(true);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("online", onOnline);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [flushDraft, payload?.assessment_id]);
  const questions = payload?.questions?.filter((item) => isQuestionVisible(item, responses)) || [];
  useEffect(() => {
    if (questions.length && index >= questions.length) setIndex(questions.length - 1);
  }, [index, questions.length]);
  useEffect(() => {
    const id = questions[Math.min(index, Math.max(questions.length - 1, 0))]?.id || null;
    if (id && currentQuestionId.current !== id) {
      currentQuestionId.current = id;
      metadataDirty.current = true;
    }
  }, [index, questions]);
  if (loading) return <><HeaderAI /><main className="page backend-state"><div className="loading-ring" /><h1>Đang lấy bộ câu hỏi từ backend</h1><p>Frontend không sử dụng câu hỏi cài sẵn.</p></main></>;
  if (error || !questions.length) return <><HeaderAI /><main className="page backend-state"><div className="empty-orbit"><span>API</span></div><div className="eyebrow">Chờ kết nối ngân hàng đề</div><h1>Chưa nhận được bộ câu hỏi</h1><p>{error || "Backend tr\u1EA3 v\u1EC1 danh s\xE1ch c\xE2u h\u1ECFi tr\u1ED1ng."}</p><button className="ghost" onClick={() => location.reload()}>Thử kết nối lại</button></main></>;
  const safeIndex = Math.min(index, questions.length - 1);
  const question = questions[safeIndex];
  const value = responses[question.id] ?? (["multi_choice", "ranking"].includes(question.type) ? [] : ["point_allocation", "tradeoff_group"].includes(question.type) ? {} : "");
  const setValue = (next) => {
    setSubmitError(null);
    dirtyQuestionIds.current.add(question.id);
    setSaveState(navigator.onLine ? "pending" : "offline");
    setResponses((current) => ({ ...current, [question.id]: next }));
  };
  const toggleOption = (option) => {
    const list = Array.isArray(value) ? value : [];
    setValue(list.includes(option) ? list.filter((item) => item !== option) : [...list, option]);
  };
  const hasAnswer = question.type === "number" ? Number.isFinite(value) && value >= (question.min ?? -Infinity) && value <= (question.max ?? Infinity) : question.type === "ranking" ? value.length === (question.required_count || 5) : question.type === "point_allocation" ? Object.values(value).reduce((sum, n) => sum + (Number(n) || 0), 0) === (question.total_points || 100) : question.type === "tradeoff_group" ? (question.items || []).every((item) => wordCount(value[item.id]) >= (question.min_words_per_item || 1) && String(value[item.id] || "").trim().length >= (question.min_chars_per_item || 1)) : ["open_text", "performance_task"].includes(question.type) ? meetsTextRequirement(question, value) : Array.isArray(value) ? value.length > 0 : String(value).trim().length > 0;
  const finish = async () => {
    const visibleResponses = Object.fromEntries(questions.filter((item) => responses[item.id] !== void 0).map((item) => [item.id, responses[item.id]]));
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await api(`${apiBase}/assessment/submit`, { method: "POST", headers: { Accept: "application/json" }, body: JSON.stringify({ assessment_id: payload.assessment_id, question_set_id: payload.question_set_id, mode: payload.mode, seed: payload.seed, responses: visibleResponses }) });
      const session = readSession();
      const nameQuestion = questions.find((item) => item.field === "display_name");
      saveSession({ displayName: nameQuestion ? String(result.responses?.[nameQuestion.id] || "").trim() || null : session.displayName, answers: { assessmentId: payload.assessment_id || null, questionSetId: payload.question_set_id, responses: result.responses }, assessmentCompleted: true, profileStatus: "ready_for_review" });
      localStorage.removeItem(ACTIVE_ASSESSMENT_KEY);
      go("/abilities");
    } catch (reason) {
      setSubmitError(reason.message);
    } finally {
      setSubmitting(false);
    }
  };
  const saveMessage = saveState === "saving" ? "\u0110ang l\u01B0u\u2026" : saveState === "pending" ? "S\u1EBD t\u1EF1 l\u01B0u trong 10 gi\xE2y" : saveState === "offline" ? "M\u1EA5t k\u1EBFt n\u1ED1i \xB7 \u0111\xE3 gi\u1EEF tr\xEAn thi\u1EBFt b\u1ECB" : saveState === "error" ? "Ch\u01B0a th\u1EC3 \u0111\u1ED3ng b\u1ED9 \xB7 s\u1EBD th\u1EED l\u1EA1i" : lastSavedAt ? `\u0110\xE3 l\u01B0u l\xFAc ${new Date(lastSavedAt).toLocaleTimeString("vi-VN")}` : "\u0110\xE3 l\u01B0u tr\xEAn thi\u1EBFt b\u1ECB";
  return <><HeaderAI /><main className="assessment page"><div className="page-top"><div><button className="back" onClick={() => safeIndex ? setIndex(safeIndex - 1) : go("/")}>← Quay lại</button><div className="eyebrow">Câu {safeIndex + 1} / {questions.length} · {question.section || "\u0110\xE1nh gi\xE1"}</div><h1>{question.prompt}</h1>{question.help_text && <p>{question.help_text}</p>}</div><div className="step-ring"><b>{safeIndex + 1}</b><span>/{questions.length}</span></div></div><Progress value={(safeIndex + 1) / questions.length * 100} /><QuestionInputV2 question={question} value={value} setValue={setValue} toggleOption={toggleOption} />{submitError && <div className="notice warning">Không thể nộp bài: {submitError}</div>}<div className="sticky-actions"><span className={`autosave-status ${saveState}`}>{saveMessage}</span><button className="primary" disabled={submitting || question.required !== false && !hasAnswer} onClick={() => safeIndex < questions.length - 1 ? setIndex(safeIndex + 1) : finish()}>{submitting ? "\u0110ang ki\u1EC3m tra..." : safeIndex < questions.length - 1 ? "Ti\u1EBFp t\u1EE5c" : "Ho\xE0n th\xE0nh kh\u1EA3o s\xE1t"} <span>→</span></button></div></main></>;
}
export {
  AssessmentPersistent
};
