const state = {
  token: localStorage.getItem("cop_token"),
  user: null,
  view: "overview",
  courses: [],
  resources: [],
  discussions: [],
  quizzes: [],
  selectedCourse: "",
  activeQuiz: null,
  quizStartedAt: null,
  quizPhase: "list",
  quizQuestions: [],
  quizIndex: 0,
  quizAnswers: {},
  quizTimerInterval: null,
  quizTimeLeft: 45,
  quizResult: null,
  quizAttempts: [],
};

const authScreen = document.querySelector("#auth-screen");
const landingView = document.querySelector("#landing-view");
const loginView = document.querySelector("#login-view");
const registerView = document.querySelector("#register-view");
const loginAlert = document.querySelector("#login-alert");
const registerAlert = document.querySelector("#register-alert");
const appScreen = document.querySelector("#app-screen");
const nav = document.querySelector("#nav");
const content = document.querySelector("#content");
const toast = document.querySelector("#toast");
const viewTitle = document.querySelector("#view-title");
const viewKicker = document.querySelector("#view-kicker");
const userName = document.querySelector("#user-name");

const navItems = [
  ["overview", "Overview"],
  ["courses", "Courses"],
  ["mycourses", "My Courses"],
  ["resources", "Resources"],
  ["discussions", "Discussions"],
  ["quizzes", "Quizzes"],
  ["surveys", "Surveys"],
  ["reflections", "Reflections"],
  ["feedback", "Feedback"],
  ["teaching", "Teaching"],
  ["research", "Research"],
];

function canResearch() {
  return state.user && ["researcher", "admin"].includes(state.user.role);
}

function canManageContent() {
  return state.user && ["facilitator", "researcher", "admin"].includes(state.user.role);
}

function isControlGroup() {
  return state.user && state.user.study_group === "control" && !canManageContent();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showMessage(text, type = "info") {
  toast.textContent = text;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  window.setTimeout(() => toast.classList.add("hidden"), 4500);
}

function showLanding() {
  authScreen.classList.remove("hidden");
  appScreen.classList.add("hidden");
  landingView.classList.remove("hidden");
  loginView.classList.add("hidden");
  registerView.classList.add("hidden");
}

function showLoginForm() {
  landingView.classList.add("hidden");
  loginView.classList.remove("hidden");
  registerView.classList.add("hidden");
  clearFormErrors("login");
}

function showRegisterForm() {
  landingView.classList.add("hidden");
  registerView.classList.remove("hidden");
  loginView.classList.add("hidden");
  clearFormErrors("register");
}

function showApp() {
  authScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  userName.textContent = `${state.user.full_name} (${state.user.research_id}) · ${state.user.study_group}`;
}

function clearFormErrors(form) {
  const prefix = form === "login" ? "login" : "register";
  const alert = document.querySelector(`#${prefix}-alert`);
  if (alert) { alert.classList.add("hidden"); alert.textContent = ""; }
  document.querySelectorAll(`#${prefix}-view .field-error`).forEach(el => { el.textContent = ""; });
  document.querySelectorAll(`#${prefix}-view input.error, #${prefix}-view select.error, #${prefix}-view textarea.error`).forEach(el => { el.classList.remove("error"); });
}

function showFieldError(form, field, msg) {
  const prefix = form === "login" ? "login" : "register";
  const span = document.querySelector(`#${prefix}-view .field-error[data-field="${field}"]`);
  if (span) { span.textContent = msg; }
  const input = document.querySelector(`#${prefix}-view [name="${field}"]`);
  if (input) { input.classList.add("error"); }
}

function showFormAlert(form, msg) {
  const prefix = form === "login" ? "login" : "register";
  const alert = document.querySelector(`#${prefix}-alert`);
  if (alert) { alert.textContent = msg; alert.classList.remove("hidden"); }
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    let fields = {};
    try {
      const error = await response.json();
      if (Array.isArray(error.detail)) {
        for (const err of error.detail) {
          const fieldName = err.loc?.[err.loc.length - 1] || "body";
          const msg = err.msg || "Invalid value";
          if (fieldName !== "body") {
            fields[fieldName] = msg;
          } else {
            detail = msg;
          }
        }
      } else {
        detail = error.detail || detail;
      }
    } catch {
      detail = response.statusText;
    }
    const err = new Error(detail);
    err.fields = fields;
    err.status = response.status;
    throw err;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function saveSession(data) {
  state.token = data.access_token;
  state.user = data.user;
  localStorage.setItem("cop_token", state.token);
}

function clearSession() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("cop_token");
  showLanding();
}

function setTitle(title, kicker = "Workspace") {
  viewTitle.textContent = title;
  viewKicker.textContent = kicker;
}

function renderNav() {
  nav.innerHTML = navItems
    .filter(([id]) => {
      if (id === "research" && !canResearch()) return false;
      if (id === "teaching" && !canManageContent()) return false;
      if (isControlGroup() && ["quizzes", "discussions"].includes(id)) return false;
      return true;
    })
    .map(
      ([id, label]) => `
        <button class="nav-btn ${state.view === id ? "active" : ""}" data-view="${id}" type="button">
          ${escapeHtml(label)}
        </button>
      `
    )
    .join("");
}

async function loadCoreData() {
  const fetchers = [api("/api/courses")];
  if (!isControlGroup()) {
    fetchers.push(api("/api/discussions?include_replies=false"));
    fetchers.push(api("/api/quizzes"));
  } else {
    fetchers.push(Promise.resolve([]));
    fetchers.push(Promise.resolve([]));
  }
  const [courses, discussions, quizzes] = await Promise.all(fetchers);
  const resources = await api("/api/resources");
  state.courses = courses;
  state.resources = resources;
  state.discussions = discussions;
  state.quizzes = quizzes;
}

function courseOptions(selected = "") {
  return state.courses
    .map(
      (course) => `
        <option value="${course.id}" ${String(selected) === String(course.id) ? "selected" : ""}>
          ${escapeHtml(course.code)} - ${escapeHtml(course.title)}
        </option>
      `
    )
    .join("");
}

function joinedCourseOptions(selected = "") {
  const joined = state.courses.filter((c) => c.is_joined);
  return joined
    .map(
      (course) => `
        <option value="${course.id}" ${String(selected) === String(course.id) ? "selected" : ""}>
          ${escapeHtml(course.code)} - ${escapeHtml(course.title)}
        </option>
      `
    )
    .join("");
}

function metric(label, value, tone = "") {
  return `
    <article class="card metric">
      <span class="muted">${escapeHtml(label)}</span>
      <strong class="${tone}">${escapeHtml(value)}</strong>
    </article>
  `;
}

function resetQuizState() {
  clearQuizTimer();
  state.quizPhase = "list";
  state.quizQuestions = [];
  state.quizIndex = 0;
  state.quizAnswers = {};
  state.quizResult = null;
  state.activeQuiz = null;
  state.quizStartedAt = null;
}

function clearQuizTimer() {
  if (state.quizTimerInterval) {
    clearInterval(state.quizTimerInterval);
    state.quizTimerInterval = null;
  }
}

function startQuizTimer() {
  clearQuizTimer();
  state.quizTimeLeft = 40;
  updateTimerDisplay();
  state.quizTimerInterval = setInterval(() => {
    state.quizTimeLeft -= 1;
    updateTimerDisplay();
    if (state.quizTimeLeft <= 0) {
      clearQuizTimer();
      handleQuestionTimeout();
    }
  }, 1000);
}

function updateTimerDisplay() {
  const bar = document.querySelector("#quiz-timer");
  if (!bar) return;
  const fill = bar.querySelector(".timer-fill");
  const text = bar.querySelector(".timer-text");
  if (fill) fill.style.width = `${(state.quizTimeLeft / 45) * 100}%`;
  if (text) text.textContent = `${state.quizTimeLeft}s`;
  bar.classList.toggle("urgent", state.quizTimeLeft <= 10);
}

function handleQuestionTimeout() {
  const question = state.quizQuestions[state.quizIndex];
  if (question) state.quizAnswers[question.id] = null;
  advanceToNextQuestion();
}

function advanceToNextQuestion() {
  state.quizIndex++;
  if (state.quizIndex >= state.quizQuestions.length) {
    submitQuizAnswers();
  } else {
    renderQuizzes();
  }
}

async function submitQuizAnswers() {
  const quiz = state.activeQuiz;
  const seconds_spent = Math.round((Date.now() - state.quizStartedAt) / 1000);
  const answers = state.quizQuestions.map((q) => ({
    question_id: q.id,
    selected_option: state.quizAnswers[q.id] || null,
  }));
  try {
    const result = await api(`/api/quizzes/${quiz.id}/submit`, {
      method: "POST",
      body: JSON.stringify({ seconds_spent, answers }),
    });
    state.quizResult = result;
    state.quizPhase = "result";
    state.activeQuiz = null;
    state.quizStartedAt = null;
    renderQuizzes();
    showMessage(`Quiz submitted. Score: ${result.score}/${result.total_points} (${result.percentage}%).`);
  } catch (error) {
    showMessage(error.message, "error");
    state.quizPhase = "list";
    renderQuizzes();
  }
}

function renderOverview() {
  setTitle("Overview", "Learning and engagement");
  const courseCount = state.courses.length;
  const resourceCount = state.resources.length;
  const discussionCount = isControlGroup() ? 0 : state.discussions.length;
  const quizCount = isControlGroup() ? 0 : state.quizzes.length;

  content.innerHTML = `
    <section class="grid">
      ${metric("Courses", courseCount)}
      ${metric("Learning Resources", resourceCount)}
      ${isControlGroup() ? "" : metric("Discussions", discussionCount)}
      ${isControlGroup() ? "" : metric("Assessments", quizCount)}
      ${metric("Research ID", state.user.research_id, "blue")}
      ${metric("Study Group", state.user.study_group)}
    </section>

    <section class="grid two">
      <article class="panel stack">
        <h2>Active Course Spaces</h2>
        <div class="list">
          ${state.courses
            .slice(0, 4)
            .map(
              (course) => `
                <div class="card compact">
                  <div class="card-header">
                    <div>
                      <h3>${escapeHtml(course.title)}</h3>
                      <p class="muted">${escapeHtml(course.description)}</p>
                    </div>
                    <span class="badge">${escapeHtml(course.code)}</span>
                  </div>
                </div>
              `
            )
            .join("")}
        </div>
      </article>
      <article class="panel stack">
        <h2>Current Assessments</h2>
        <div class="list">
          ${state.quizzes
            .slice(0, 4)
            .map(
              (quiz) => `
                <div class="card compact">
                  <div class="card-header">
                    <div>
                      <h3>${escapeHtml(quiz.title)}</h3>
                      <p class="muted">${escapeHtml(quiz.description || "")}</p>
                    </div>
                    <span class="badge gold">${escapeHtml(quiz.quiz_type)}</span>
                  </div>
                </div>
              `
            )
            .join("")}
        </div>
      </article>
    </section>
  `;
}

function renderCourses() {
  setTitle("Courses", "Community spaces");
  content.innerHTML = `
    <section class="list">
      ${state.courses
        .map(
          (course) => `
            <article class="card">
              <div class="card-header">
                <div>
                  <div class="badge-row">
                    <span class="badge">${escapeHtml(course.code)}</span>
                    <span class="badge blue">${course.member_count} members</span>
                    <span class="badge">${course.resource_count} resources</span>
                  </div>
                  <h2>${escapeHtml(course.title)}</h2>
                  <p class="muted">${escapeHtml(course.description)}</p>
                </div>
                <button data-action="join-course" data-id="${course.id}" type="button">Join</button>
              </div>
              <form class="toolbar" data-form="join-course" data-id="${course.id}">
                <input name="learning_goal" placeholder="Learning goal for this course" />
                <button class="secondary" type="submit">Save Goal</button>
              </form>
            </article>
          `
        )
        .join("")}
    </section>
  `;
}

function renderMyCourses() {
  setTitle("My Courses", "Your learning spaces");
  const joined = state.courses.filter((c) => c.is_joined);

  if (!joined.length) {
    content.innerHTML = `
      <section class="stack">
        <div class="empty">You have not joined any courses yet. Go to <a href="#" data-nav="courses">Courses</a> to browse and join courses.</div>
      </section>
    `;
    return;
  }

  content.innerHTML = `<section class="stack"><div class="empty">Loading progress...</div></section>`;

  loadMyCoursesProgress(joined);
}

async function loadMyCoursesProgress(joined) {
  const progressMap = {};
  const promises = joined.map(async (course) => {
    try {
      progressMap[course.id] = await api(`/api/courses/${course.id}/progress`);
    } catch {
      progressMap[course.id] = null;
    }
  });
  await Promise.all(promises);

  content.innerHTML = joined
    .map((course) => {
      const courseResources = state.resources.filter((r) => String(r.course_id) === String(course.id));
      const courseQuizzes = state.quizzes.filter((q) => String(q.course_id) === String(course.id));
      const courseDiscussions = state.discussions.filter((d) => String(d.course_id) === String(course.id));
      const progress = progressMap[course.id] || {};

      const resourcePct = progress.resource_count ? Math.round((progress.resources_viewed || 0) / progress.resource_count * 100) : 0;
      const quizPct = progress.quiz_count ? Math.round((progress.quizzes_taken || 0) / progress.quiz_count * 100) : 0;
      const quizAvg = progress.quiz_average_percentage != null ? `${progress.quiz_average_percentage}% avg` : "";

      return `
        <article class="card stack">
          <div class="card-header">
            <div>
              <div class="badge-row">
                <span class="badge">${escapeHtml(course.code)}</span>
                <span class="badge blue">${course.member_count} members</span>
                <span class="badge">${course.resource_count} resources</span>
              </div>
              <h2>${escapeHtml(course.title)}</h2>
              <p class="muted">${escapeHtml(course.description)}</p>
            </div>
          </div>

          <div class="progress-row">
            <div class="progress-item" title="Resources viewed">
              <span class="muted">Resources</span>
              <div class="progress-bar"><div class="progress-fill" style="width:${resourcePct}%"></div></div>
              <small>${progress.resources_viewed || 0}/${progress.resource_count || 0}</small>
            </div>
            ${
              !isControlGroup()
                ? `
            <div class="progress-item" title="Quizzes taken">
              <span class="muted">Quizzes</span>
              <div class="progress-bar"><div class="progress-fill gold" style="width:${quizPct}%"></div></div>
              <small>${progress.quizzes_taken || 0}/${progress.quiz_count || 0} ${quizAvg}</small>
            </div>
            <div class="progress-item" title="Discussion participation">
              <span class="muted">Discussions</span>
              <div class="progress-bar"><div class="progress-fill blue" style="width:100%"></div></div>
              <small>${progress.discussions_participated || 0} posts</small>
            </div>
                `
                : ""
            }
          </div>

          <details open>
            <summary><strong>Resources</strong> <span class="badge">${courseResources.length}</span></summary>
            <div class="list" style="margin-top:10px">
              ${
                courseResources.length
                  ? courseResources
                      .map(
                        (r) => `
                          <div class="card compact">
                            <div class="card-header">
                              <div>
                                <div class="badge-row">
                                  <span class="badge">${escapeHtml(r.resource_type)}</span>
                                  <span class="badge gold">${escapeHtml(r.difficulty)}</span>
                                  <span class="badge">${r.estimated_minutes} min</span>
                                </div>
                                <h3>${escapeHtml(r.title)}</h3>
                                <p class="muted">${escapeHtml(r.body || r.url || "")}</p>
                              </div>
                              <button data-action="view-resource" data-id="${r.id}" type="button">Record View</button>
                            </div>
                          </div>
                        `
                      )
                      .join("")
                  : `<div class="empty">No resources yet.</div>`
              }
            </div>
          </details>

          ${
            !isControlGroup()
              ? `
          <details open>
            <summary><strong>Quizzes</strong> <span class="badge">${courseQuizzes.length}</span></summary>
            <div class="list" style="margin-top:10px">
              ${
                courseQuizzes.length
                  ? courseQuizzes
                      .map(
                        (q) => `
                          <div class="card compact">
                            <div class="card-header">
                              <div>
                                <div class="badge-row">
                                  <span class="badge gold">${escapeHtml(q.quiz_type)}</span>
                                  <span class="badge">${q.question_count} questions</span>
                                  <span class="badge blue">${escapeHtml(q.round_size || q.question_count)} per round</span>
                                </div>
                                <h3>${escapeHtml(q.title)}</h3>
                                <p class="muted">${escapeHtml(q.description || "")}</p>
                              </div>
                              <button data-action="open-quiz" data-id="${q.id}" type="button">Open</button>
                            </div>
                          </div>
                        `
                      )
                      .join("")
                  : `<div class="empty">No quizzes yet.</div>`
              }
            </div>
          </details>

          <details open>
            <summary><strong>Discussions</strong> <span class="badge">${courseDiscussions.length}</span></summary>
            <div class="list" style="margin-top:10px">
              ${
                courseDiscussions.length
                  ? courseDiscussions
                      .map(
                        (t) => `
                          <div class="card compact">
                            <div class="card-header">
                              <div>
                                <div class="badge-row">
                                  <span class="badge">${t.reply_count} replies</span>
                                  ${t.is_resolved ? `<span class="badge gold">resolved</span>` : `<span class="badge">open</span>`}
                                </div>
                                <h3>${escapeHtml(t.title)}</h3>
                                <p>${escapeHtml(t.body)}</p>
                                <p class="muted">${escapeHtml(t.author_name || "Student")} ${t.tags ? `· ${escapeHtml(t.tags)}` : ""}</p>
                              </div>
                              <button class="secondary" data-action="load-thread" data-id="${t.id}" type="button">Open</button>
                            </div>
                          </div>
                        `
                      )
                      .join("")
                  : `<div class="empty">No discussions yet.</div>`
              }
            </div>
          </details>
              `
              : ""
          }
        </article>
      `;
    })
    .join("");
}

function renderResources() {
  setTitle("Resources", "Learning materials");
  const filtered = state.selectedCourse
    ? state.resources.filter((resource) => String(resource.course_id) === String(state.selectedCourse))
    : state.resources;

  content.innerHTML = `
    <section class="toolbar">
      <select id="course-filter">
        <option value="">All courses</option>
        ${canManageContent() ? courseOptions(state.selectedCourse) : joinedCourseOptions(state.selectedCourse)}
      </select>
    </section>

    <section class="split">
      <div class="list">
        ${
          filtered.length
            ? filtered
                .map(
                  (resource) => `
                    <article class="card stack">
                      <div class="card-header">
                        <div>
                          <div class="badge-row">
                            <span class="badge">${escapeHtml(resource.resource_type)}</span>
                            <span class="badge gold">${escapeHtml(resource.difficulty)}</span>
                            <span class="badge">${resource.estimated_minutes} min</span>
                          </div>
                          <h2>${escapeHtml(resource.title)}</h2>
                          <p class="muted">${escapeHtml(resource.body || resource.url || "")}</p>
                          ${resource.url ? `<p class="muted"><a href="${escapeHtml(resource.url)}" target="_blank">Textbook Link</a></p>` : ""}
                          ${resource.video_url ? `<p class="muted"><a href="${escapeHtml(resource.video_url)}" target="_blank">YouTube Videos</a></p>` : ""}
                          ${resource.blog_url ? `<p class="muted"><a href="${escapeHtml(resource.blog_url)}" target="_blank">Blog Posts</a></p>` : ""}
                        </div>
                        <button data-action="view-resource" data-id="${resource.id}" type="button">Record View</button>
                      </div>
                      <form class="toolbar" data-form="resource-feedback" data-id="${resource.id}">
                        <select name="usefulness_rating" aria-label="Usefulness">
                          <option value="5">Usefulness 5</option>
                          <option value="4">Usefulness 4</option>
                          <option value="3">Usefulness 3</option>
                          <option value="2">Usefulness 2</option>
                          <option value="1">Usefulness 1</option>
                        </select>
                        <select name="clarity_rating" aria-label="Clarity">
                          <option value="5">Clarity 5</option>
                          <option value="4">Clarity 4</option>
                          <option value="3">Clarity 3</option>
                          <option value="2">Clarity 2</option>
                          <option value="1">Clarity 1</option>
                        </select>
                        <input name="comment" placeholder="Short feedback" />
                        <button class="secondary" type="submit">Send Feedback</button>
                      </form>
                    </article>
                  `
                )
                .join("")
            : `<div class="empty">No resources found for this filter.</div>`
        }
      </div>

      ${
        canManageContent()
          ? `
            <form class="panel form-stack" data-form="create-resource">
              <h2>Add Resource</h2>
              <label>Course <select name="course_id">${courseOptions()}</select></label>
              <label>Title <input name="title" required /></label>
              <div class="two-col">
                <label>Type <input name="resource_type" value="note" /></label>
                <label>Difficulty <input name="difficulty" value="beginner" /></label>
              </div>
              <label>Estimated Minutes <input name="estimated_minutes" type="number" min="1" value="15" /></label>
              <label>URL <input name="url" /></label>
              <label>Video URL <input name="video_url" /></label>
              <label>Blog URL <input name="blog_url" /></label>
              <label>Body <textarea name="body" rows="5"></textarea></label>
              <button type="submit">Add Resource</button>
            </form>
          `
          : `<aside class="panel"><h2>Resource Feedback</h2><p class="muted">Ratings and comments here become analyzable perception data.</p></aside>`
      }
    </section>
  `;
}

function renderDiscussions() {
  setTitle("Discussions", "Peer learning");
  content.innerHTML = `
    <section class="split">
      <div class="list">
        ${
          state.discussions.length
            ? state.discussions
                .map(
                  (thread) => `
                    <article class="card stack">
                      <div class="card-header">
                        <div>
                          <div class="badge-row">
                            <span class="badge">${thread.reply_count} replies</span>
                            ${thread.is_resolved ? `<span class="badge gold">resolved</span>` : `<span class="badge">open</span>`}
                          </div>
                          <h2>${escapeHtml(thread.title)}</h2>
                          <p>${escapeHtml(thread.body)}</p>
                          <p class="muted">${escapeHtml(thread.author_name || "Student")} ${thread.tags ? `· ${escapeHtml(thread.tags)}` : ""}</p>
                        </div>
                        <button class="secondary" data-action="load-thread" data-id="${thread.id}" type="button">Open</button>
                      </div>
                      <div class="list" id="thread-${thread.id}">
                        ${(thread.replies || [])
                          .map(
                            (reply) => `
                              <div class="card compact">
                                <p>${escapeHtml(reply.body)}</p>
                                <div class="toolbar">
                                  <span class="muted">${escapeHtml(reply.author_name || "Student")}</span>
                                  <button class="secondary" data-action="helpful" data-id="${reply.id}" type="button">Helpful ${reply.helpful_count}</button>
                                </div>
                              </div>
                            `
                          )
                          .join("")}
                      </div>
                      <form class="toolbar" data-form="reply" data-id="${thread.id}">
                        <input name="body" placeholder="Reply to this discussion" required />
                        <button type="submit">Reply</button>
                      </form>
                    </article>
                  `
                )
                .join("")
            : `<div class="empty">No discussions yet.</div>`
        }
      </div>

      <form class="panel form-stack" data-form="create-discussion">
        <h2>Start Discussion</h2>
        <label>Course <select name="course_id">${canManageContent() ? courseOptions() : joinedCourseOptions()}</select></label>
        <label>Title <input name="title" required /></label>
        <label>Question or Idea <textarea name="body" rows="5" required></textarea></label>
        <label>Tags <input name="tags" placeholder="python, debugging, sql" /></label>
        <button type="submit">Post Discussion</button>
      </form>
    </section>
  `;
}

function renderQuizzes() {
  setTitle("Quizzes", "Academic performance");

  if (state.quizPhase === "active") {
    renderQuizActive();
    return;
  }
  if (state.quizPhase === "result" && state.quizResult) {
    renderQuizResults();
    return;
  }
  renderQuizList();
}

function renderQuizList() {
  content.innerHTML = `
    <section class="split">
      <div class="list">
        ${state.quizzes
          .map(
            (quiz) => `
              <article class="card">
                <div class="card-header">
                  <div>
                    <div class="badge-row">
                      <span class="badge gold">${escapeHtml(quiz.quiz_type)}</span>
                      <span class="badge">${quiz.question_count} questions</span>
                      <span class="badge blue">${escapeHtml(quiz.round_size || quiz.question_count)} per round</span>
                    </div>
                    <h2>${escapeHtml(quiz.title)}</h2>
                    <p class="muted">${escapeHtml(quiz.description || "")}</p>
                  </div>
                  <button data-action="open-quiz" data-id="${quiz.id}" type="button">Open</button>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
      <aside class="panel stack">
        <h2>Quiz Results</h2>
        <p class="muted">View your past quiz attempts and detailed results.</p>
        <button data-action="quiz-history" type="button">View History</button>
      </aside>
    </section>
  `;
}

function renderQuizActive() {
  const question = state.quizQuestions[state.quizIndex];
  if (!question) {
    state.quizPhase = "list";
    renderQuizList();
    return;
  }
  const total = state.quizQuestions.length;
  const current = state.quizIndex + 1;

  content.innerHTML = `
    <section class="panel stack quiz-active">
      <div class="quiz-progress-row">
        <span class="muted">Question ${current} of ${total}</span>
        <div id="quiz-timer" class="timer-bar">
          <div class="timer-fill" style="width:100%"></div>
          <span class="timer-text">45s</span>
        </div>
      </div>
      <h2>${escapeHtml(question.prompt)}</h2>
      <div class="quiz-options" data-question-id="${question.id}">
        ${["a", "b", "c", "d"]
          .map(
            (opt) => `
              <label class="quiz-option">
                <input type="radio" name="quiz-answer" value="${opt}" />
                <span>${opt.toUpperCase()}. ${escapeHtml(question[`option_${opt}`])}</span>
              </label>
            `
          )
          .join("")}
      </div>
    </section>
  `;

  startQuizTimer();
}

function renderQuizResults() {
  const r = state.quizResult;
  if (!r) {
    state.quizPhase = "list";
    renderQuizList();
    return;
  }

  content.innerHTML = `
    <section class="stack">
      <article class="panel stack">
        <div class="grid two">
          <div class="metric">
            <span class="muted">Score</span>
            <strong>${escapeHtml(r.score)} / ${escapeHtml(r.total_points)}</strong>
          </div>
          <div class="metric">
            <span class="muted">Percentage</span>
            <strong class="${r.percentage >= 50 ? "" : "danger"}">${escapeHtml(r.percentage)}%</strong>
          </div>
          <div class="metric">
            <span class="muted">Questions</span>
            <strong>${escapeHtml(r.question_count)}</strong>
          </div>
          <div class="metric">
            <span class="muted">Time Spent</span>
            <strong>${escapeHtml(r.seconds_spent)}s</strong>
          </div>
        </div>
        <div class="toolbar">
          <span class="badge gold">${escapeHtml(r.quiz_type)}</span>
          <span class="badge blue">${escapeHtml(r.quiz_title)}</span>
        </div>
      </article>

      <article class="panel stack">
        <h2>Question Details</h2>
        <div class="list">
          ${(r.answers || [])
            .map(
              (answer, idx) => `
                <div class="card compact ${answer.is_correct ? "correct" : "wrong"}">
                  <div class="badge-row">
                    <span class="badge ${answer.is_correct ? "blue" : "gold"}">
                      ${answer.is_correct ? "Correct" : "Wrong"}
                    </span>
                    <span class="badge">${escapeHtml(answer.points_awarded)} / ${escapeHtml(answer.points)} pts</span>
                  </div>
                  <p><strong>${idx + 1}. ${escapeHtml(answer.prompt)}</strong></p>
                  <p class="muted">
                    Your answer: <strong>${answer.selected_option ? answer.selected_option.toUpperCase() + ". " + escapeHtml(answer.options?.[answer.selected_option] || "") : "No answer (timeout)"}</strong>
                  </p>
                  ${!answer.is_correct ? `<p class="muted">Correct answer: <strong>${answer.correct_option.toUpperCase()}. ${escapeHtml(answer.options?.[answer.correct_option] || "")}</strong></p>` : ""}
                  ${answer.explanation ? `<p class="muted">${escapeHtml(answer.explanation)}</p>` : ""}
                </div>
              `
            )
            .join("")}
        </div>
      </article>

      <div class="toolbar">
        <button data-action="back-to-quizzes" type="button">Back to Quizzes</button>
        <button class="secondary" data-action="quiz-history" type="button">View All Results</button>
      </div>
    </section>
  `;
}

function renderReflections() {
  setTitle("Reflections", "Weekly learning journal");
  content.innerHTML = `
    <form class="panel form-stack" data-form="reflection">
      <div class="two-col">
        <label>Week <input name="week_label" placeholder="Week 1" required /></label>
        <label>Confidence
          <select name="confidence_rating">
            <option value="5">5 - Very high</option>
            <option value="4">4 - High</option>
            <option value="3">3 - Moderate</option>
            <option value="2">2 - Low</option>
            <option value="1">1 - Very low</option>
          </select>
        </label>
      </div>
      <label>Engagement
        <select name="engagement_rating">
          <option value="5">5 - Very engaged</option>
          <option value="4">4 - Engaged</option>
          <option value="3">3 - Moderate</option>
          <option value="2">2 - Low</option>
          <option value="1">1 - Very low</option>
        </select>
      </label>
      <label>What did you learn? <textarea name="learned" rows="4" required></textarea></label>
      <label>What was difficult? <textarea name="challenge" rows="3"></textarea></label>
      <label>How did the community help? <textarea name="community_help" rows="3"></textarea></label>
      <label>Suggestions <textarea name="suggestions" rows="3"></textarea></label>
      <button type="submit">Save Reflection</button>
    </form>
  `;
}

async function renderSurveys() {
  setTitle("Surveys", "Research instruments");
  const surveys = await api("/api/surveys");
  content.innerHTML = `
    <section class="list">
      ${surveys
        .map(
          (s) => `
            <article class="card">
              <div class="card-header">
                <div>
                  <div class="badge-row">
                    <span class="badge gold">${escapeHtml(s.survey_type)}</span>
                    <span class="badge">${s.question_count} questions</span>
                  </div>
                  <h2>${escapeHtml(s.title)}</h2>
                  <p class="muted">${escapeHtml(s.description || "")}</p>
                </div>
                <button data-action="open-survey" data-id="${s.id}" type="button">${s.user_has_responded ? "View" : "Start"}</button>
              </div>
            </article>
          `
        )
        .join("")}
    </section>
  `;
}

function renderSurveyActive(survey) {
  setTitle(survey.title, "Research instrument");
  content.innerHTML = `
    <form class="panel form-stack" data-form="survey-submit" data-id="${survey.id}">
      ${(survey.questions || [])
        .map(
          (q, idx) => `
            <label>
              <strong>${idx + 1}. ${escapeHtml(q.prompt)}</strong>
              <select name="${q.id}" required>
                <option value="">Select rating (1-5)</option>
                <option value="5">5 - Strongly Agree</option>
                <option value="4">4 - Agree</option>
                <option value="3">3 - Neutral</option>
                <option value="2">2 - Disagree</option>
                <option value="1">1 - Strongly Disagree</option>
              </select>
            </label>
          `
        )
        .join("")}
      <button type="submit">Submit Survey</button>
    </form>
  `;
}

function renderFeedback() {
  setTitle("Feedback", "Platform experience");
  content.innerHTML = `
    <form class="panel form-stack" data-form="platform-feedback">
      <div class="two-col">
        <label>Category
          <select name="category">
            <option value="usability">Usability</option>
            <option value="learning_support">Learning Support</option>
            <option value="community">Community</option>
            <option value="content">Content</option>
            <option value="general">General</option>
          </select>
        </label>
        <label>Rating
          <select name="rating">
            <option value="5">5 - Excellent</option>
            <option value="4">4 - Good</option>
            <option value="3">3 - Fair</option>
            <option value="2">2 - Weak</option>
            <option value="1">1 - Poor</option>
          </select>
        </label>
      </div>
      <label>Comment <textarea name="comment" rows="5"></textarea></label>
      <button type="submit">Submit Feedback</button>
    </form>
  `;
}

async function renderTeaching() {
  setTitle("Teaching", "Instructor dashboard");
  content.innerHTML = `<div class="empty">Loading instructor dashboard...</div>`;
  const courses = await api("/api/instructor/courses");

  content.innerHTML = `
    <section class="list">
      ${courses
        .map(
          (c) => `
            <article class="card">
              <div class="card-header">
                <div>
                  <div class="badge-row">
                    <span class="badge">${escapeHtml(c.code)}</span>
                    <span class="badge blue">${c.member_count} students</span>
                    <span class="badge">${c.resource_count} resources</span>
                    <span class="badge gold">${c.quiz_count} quizzes</span>
                    <span class="badge">${c.discussion_count} discussions</span>
                  </div>
                  <h2>${escapeHtml(c.title)}</h2>
                </div>
                <button data-action="course-stats" data-id="${c.id}" type="button">Stats</button>
              </div>
            </article>
          `
        )
        .join("")}
    </section>
  `;
}

function renderCourseStats(stats) {
  setTitle(`${stats.course_code} Stats`, "Instructor dashboard");
  content.innerHTML = `
    <section class="stack">
      <article class="panel stack">
        <h2>${escapeHtml(stats.course_title)}</h2>
        <div class="grid">
          ${metric("Students", stats.member_count)}
          ${metric("Experimental", stats.experimental_count, "blue")}
          ${metric("Control", stats.control_count)}
          ${metric("Quiz Attempts", stats.quiz_attempts)}
          ${metric("Avg Quiz %", stats.quiz_average_percentage != null ? stats.quiz_average_percentage + "%" : "N/A")}
          ${metric("Resource Views", stats.resource_view_count)}
          ${metric("Threads", stats.thread_count)}
          ${metric("Replies", stats.reply_count)}
        </div>
        ${
          stats.quiz_breakdown && Object.keys(stats.quiz_breakdown).length
            ? `
              <div class="badge-row">
                ${Object.entries(stats.quiz_breakdown)
                  .map(([k, v]) => `<span class="badge gold">${escapeHtml(k)}: ${v}% avg</span>`)
                  .join("")}
              </div>
            `
            : ""
        }
      </article>

      ${
        stats.recent_attempts && stats.recent_attempts.length
          ? `
            <article class="panel stack">
              <h2>Recent Quiz Attempts</h2>
              <div class="list">
                ${stats.recent_attempts
                  .map(
                    (a) => `
                      <div class="card compact">
                        <div class="card-header">
                          <div>
                            <div class="badge-row">
                              <span class="badge blue">${escapeHtml(a.research_id)}</span>
                              <span class="badge">${escapeHtml(a.user_name)}</span>
                              <span class="badge gold">${escapeHtml(a.quiz_type)}</span>
                            </div>
                            <p><strong>${escapeHtml(a.quiz_title)}</strong></p>
                            <p class="muted">Score: ${a.score}/${a.total_points} (${a.percentage}%) &middot; Study group: ${escapeHtml(a.study_group)}</p>
                          </div>
                        </div>
                      </div>
                    `
                  )
                  .join("")}
              </div>
            </article>
          `
          : ""
      }

      <div class="toolbar">
        <button data-action="back-to-teaching" type="button">Back to Courses</button>
      </div>
    </section>
  `;
}

async function renderResearch() {
  setTitle("Research", "Analytics and exports");
  content.innerHTML = `<div class="empty">Loading research dashboard...</div>`;
  const [dashboard, users] = await Promise.all([api("/api/research/dashboard"), api("/api/research/users")]);

  content.innerHTML = `
    <section class="grid">
      ${metric("Participants", dashboard.users)}
      ${metric("Experimental", dashboard.experimental_users)}
      ${metric("Control", dashboard.control_users)}
      ${metric("Quiz Attempts", dashboard.quiz_attempts)}
      ${metric("Average Quiz %", dashboard.average_quiz_percentage)}
      ${metric("Engagement Avg", dashboard.average_engagement_rating)}
      ${metric("Activity Events", dashboard.activity_events)}
      ${metric("Feedback Items", dashboard.feedback_items)}
      ${metric("Reflections", dashboard.reflections)}
    </section>

    <section class="split">
      <article class="panel stack">
        <h2>CSV Exports</h2>
        <div class="export-grid">
          ${["users", "activity", "quiz_attempts", "feedback", "reflections", "discussions", "academic_records", "combined"]
            .map((dataset) => `<button class="secondary" data-action="export" data-id="${dataset}" type="button">${dataset.replaceAll("_", " ")}</button>`)
            .join("")}
        </div>
      </article>

      <form class="panel form-stack" data-form="academic-record">
        <h2>Add Academic Record</h2>
        <label>Student
          <select name="user_id">
            ${users
              .filter((user) => user.role === "student")
              .map((user) => `<option value="${user.id}">${escapeHtml(user.research_id)} - ${escapeHtml(user.full_name)}</option>`)
              .join("")}
          </select>
        </label>
        <label>Assessment <input name="assessment_name" placeholder="Course exam, assignment, post-test" required /></label>
        <div class="two-col">
          <label>Type <input name="assessment_type" value="external" /></label>
          <label>Score <input name="score" type="number" min="0" step="0.01" required /></label>
        </div>
        <label>Total <input name="total" type="number" min="1" step="0.01" value="100" required /></label>
        <label>Notes <textarea name="notes" rows="3"></textarea></label>
        <button type="submit">Save Record</button>
      </form>
    </section>
  `;
}

async function render() {
  renderNav();
  if (state.view === "overview") renderOverview();
  if (state.view === "courses") renderCourses();
  if (state.view === "mycourses") renderMyCourses();
  if (state.view === "resources") renderResources();
  if (state.view === "discussions") renderDiscussions();
  if (state.view === "quizzes") renderQuizzes();
  if (state.view === "surveys") await renderSurveys();
  if (state.view === "reflections") renderReflections();
  if (state.view === "feedback") renderFeedback();
  if (state.view === "teaching") await renderTeaching();
  if (state.view === "research") await renderResearch();
}

async function refreshAndRender() {
  await loadCoreData();
  await render();
}

async function refreshCourses() {
  state.courses = await api("/api/courses");
}

async function refreshDiscussions() {
  state.discussions = await api("/api/discussions?include_replies=false");
}

async function refreshQuizzes() {
  state.quizzes = await api("/api/quizzes");
}

async function setView(view) {
  state.view = view;
  if (view !== "quizzes") {
    resetQuizState();
  }
  await render();
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFormErrors("login");
  try {
    const payload = formData(event.currentTarget);
    const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(payload) });
    saveSession(data);
    showApp();
    await refreshAndRender();
    showMessage("Signed in.");
  } catch (error) {
    if (error.fields && Object.keys(error.fields).length) {
      for (const [field, msg] of Object.entries(error.fields)) {
        showFieldError("login", field, msg);
      }
    } else {
      showFormAlert("login", error.message || "Invalid email or password.");
    }
  }
});

document.querySelector("#register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFormErrors("register");
  try {
    const payload = formData(event.currentTarget);
    payload.accepted_research_consent = event.currentTarget.accepted_research_consent.checked;
    const data = await api("/api/auth/register", { method: "POST", body: JSON.stringify(payload) });
    saveSession(data);
    showApp();
    await refreshAndRender();
    showMessage("Account created.");
  } catch (error) {
    if (error.fields && Object.keys(error.fields).length) {
      for (const [field, msg] of Object.entries(error.fields)) {
        showFieldError("register", field, msg);
      }
    } else {
      showFormAlert("register", error.message || "Registration failed.");
    }
  }
});

document.querySelector("#logout-btn").addEventListener("click", clearSession);

let notificationPollInterval = null;

async function updateNotificationBadge() {
  try {
    const data = await api("/api/notifications");
    const badge = document.querySelector("#notif-count");
    if (data.unread_count > 0) {
      badge.textContent = data.unread_count > 99 ? "99+" : data.unread_count;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  } catch {}
}

document.querySelector("#notification-btn").addEventListener("click", async () => {
  try {
    const data = await api("/api/notifications");
    content.innerHTML = `
      <section class="stack">
        <div class="toolbar">
          <h2 style="margin:0">Notifications</h2>
          <button data-action="mark-all-read" type="button" class="secondary">Mark All Read</button>
        </div>
        <div class="list">
          ${
            data.items.length
              ? data.items
                  .map(
                    (n) => `
                      <div class="card compact ${n.is_read ? "" : "unread"}">
                        <div class="card-header">
                          <div>
                            <p>${escapeHtml(n.message)}</p>
                            <p class="muted">${new Date(n.created_at).toLocaleString()}</p>
                          </div>
                          ${!n.is_read ? `<button data-action="mark-read" data-id="${n.id}" type="button" class="secondary">Read</button>` : ""}
                        </div>
                      </div>
                    `
                  )
                  .join("")
              : `<div class="empty">No notifications yet.</div>`
          }
        </div>
      </section>
    `;
  } catch {
    showMessage("Could not load notifications.", "error");
  }
});

async function startNotificationPolling() {
  if (notificationPollInterval) clearInterval(notificationPollInterval);
  await updateNotificationBadge();
  notificationPollInterval = setInterval(updateNotificationBadge, 30000);
}

nav.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-view]");
  if (!button) return;
  await setView(button.dataset.view);
});

content.addEventListener("change", async (event) => {
  if (event.target.id === "course-filter") {
    state.selectedCourse = event.target.value;
    renderResources();
  }

  if (event.target.name === "quiz-answer" && state.quizPhase === "active") {
    const options = event.target.closest(".quiz-options");
    if (!options) return;
    const questionId = Number(options.dataset.questionId);
    state.quizAnswers[questionId] = event.target.value;
    clearQuizTimer();
    setTimeout(() => advanceToNextQuestion(), 400);
  }
});

authScreen.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  if (action === "show-login") { showLoginForm(); return; }
  if (action === "show-register") { showRegisterForm(); return; }
  if (action === "back-to-landing") { showLanding(); return; }
});

content.addEventListener("click", async (event) => {
  const navLink = event.target.closest("[data-nav]");
  if (navLink) {
    event.preventDefault();
    await setView(navLink.dataset.nav);
    return;
  }

  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  const id = button.dataset.id;

  try {
    if (action === "join-course") {
      await api(`/api/courses/${id}/join`, { method: "POST", body: JSON.stringify({}) });
      await refreshCourses();
      render();
      showMessage("Course joined.");
    }

    if (action === "view-resource") {
      await api(`/api/resources/${id}?seconds_spent=30`);
      state.resources = await api("/api/resources");
      render();
      showMessage("Resource view recorded.");
    }

    if (action === "load-thread") {
      const thread = await api(`/api/discussions/${id}`);
      const idx = state.discussions.findIndex((d) => d.id === thread.id);
      if (idx >= 0) {
        state.discussions[idx] = thread;
      } else {
        state.discussions.push(thread);
      }
      render();
    }

    if (action === "helpful") {
      await api(`/api/replies/${id}/helpful`, { method: "POST" });
      for (const thread of state.discussions) {
        for (const reply of (thread.replies || [])) {
          if (reply.id === Number(id)) {
            reply.helpful_count += 1;
            break;
          }
        }
      }
      render();
      showMessage("Helpful vote recorded.");
    }

    if (action === "open-quiz") {
      const quiz = await api(`/api/quizzes/${id}`);
      state.view = "quizzes";
      state.activeQuiz = quiz;
      state.quizQuestions = quiz.questions || [];
      state.quizIndex = 0;
      state.quizAnswers = {};
      state.quizPhase = "active";
      state.quizStartedAt = Date.now();
      renderNav();
      renderQuizzes();
    }

    if (action === "quiz-history") {
      const attempts = await api("/api/quiz-attempts");
      state.quizAttempts = attempts;
      if (state.quizResult) {
        renderQuizResults();
        showMessage(`${attempts.length} total attempt(s).`);
      } else {
        renderQuizHistoryList(attempts);
      }
    }

    if (action === "view-attempt") {
      const result = await api(`/api/quiz-attempts/${id}`);
      state.quizResult = result;
      state.quizPhase = "result";
      renderQuizzes();
    }

    if (action === "back-to-quizzes") {
      resetQuizState();
      state.view = "quizzes";
      await refreshQuizzes();
      renderNav();
      renderQuizList();
    }

    if (action === "export") {
      await downloadDataset(id);
    }

    if (action === "open-survey") {
      const survey = await api(`/api/surveys/${id}`);
      renderSurveyActive(survey);
    }

    if (action === "course-stats") {
      const stats = await api(`/api/instructor/courses/${id}/stats`);
      renderCourseStats(stats);
    }

    if (action === "back-to-teaching") {
      await setView("teaching");
    }

    if (action === "mark-read") {
      await api(`/api/notifications/${id}/read`, { method: "POST" });
      await updateNotificationBadge();
      document.querySelector("#notification-btn").click();
    }

    if (action === "mark-all-read") {
      await api("/api/notifications/read-all", { method: "POST" });
      await updateNotificationBadge();
      document.querySelector("#notification-btn").click();
    }
  } catch (error) {
    showMessage(error.message, "error");
  }
});

content.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  const type = form.dataset.form;

  try {
    if (type === "join-course") {
      await api(`/api/courses/${form.dataset.id}/join`, {
        method: "POST",
        body: JSON.stringify(formData(form)),
      });
      await refreshCourses();
      render();
      showMessage("Learning goal saved.");
    }

    if (type === "resource-feedback") {
      const payload = formData(form);
      payload.usefulness_rating = Number(payload.usefulness_rating);
      payload.clarity_rating = Number(payload.clarity_rating);
      await api(`/api/resources/${form.dataset.id}/feedback`, { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      showMessage("Resource feedback recorded.");
    }

    if (type === "create-resource") {
      const payload = formData(form);
      payload.course_id = Number(payload.course_id);
      payload.estimated_minutes = Number(payload.estimated_minutes || 15);
      await api("/api/resources", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      state.resources = await api("/api/resources");
      await refreshCourses();
      render();
      showMessage("Resource added.");
    }

    if (type === "create-discussion") {
      const payload = formData(form);
      payload.course_id = Number(payload.course_id);
      await api("/api/discussions", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      await refreshDiscussions();
      render();
      showMessage("Discussion posted.");
    }

    if (type === "reply") {
      await api(`/api/discussions/${form.dataset.id}/replies`, {
        method: "POST",
        body: JSON.stringify(formData(form)),
      });
      form.reset();
      await refreshDiscussions();
      render();
      showMessage("Reply posted.");
    }

    if (type === "reflection") {
      const payload = formData(form);
      payload.confidence_rating = Number(payload.confidence_rating);
      payload.engagement_rating = Number(payload.engagement_rating);
      await api("/api/reflections", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      showMessage("Reflection saved.");
    }

    if (type === "platform-feedback") {
      const payload = formData(form);
      payload.rating = Number(payload.rating);
      await api("/api/feedback", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      showMessage("Feedback submitted.");
    }

    if (type === "academic-record") {
      const payload = formData(form);
      payload.user_id = Number(payload.user_id);
      payload.score = Number(payload.score);
      payload.total = Number(payload.total);
      await api("/api/academic-records", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      await renderResearch();
      showMessage("Academic record saved.");
    }

    if (type === "survey-submit") {
      const surveyId = Number(form.dataset.id);
      const answers = [];
      let allAnswered = true;
      for (const el of form.querySelectorAll("select")) {
        if (!el.value) { allAnswered = false; break; }
        answers.push({ question_id: Number(el.name), rating: Number(el.value) });
      }
      if (!allAnswered) {
        showMessage("Please answer all questions.", "error");
        return;
      }
      await api(`/api/surveys/${surveyId}/submit`, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      await setView("surveys");
      showMessage("Survey submitted. Thank you.");
    }
  } catch (error) {
    showMessage(error.message, "error");
  }
});

function renderQuizHistoryList(attempts) {
  setTitle("Quiz History", "Past attempts");
  if (!attempts.length) {
    content.innerHTML = `
      <section class="panel stack">
        <div class="empty">No quiz attempts yet.</div>
        <button data-action="back-to-quizzes" type="button">Back to Quizzes</button>
      </section>
    `;
    return;
  }
  content.innerHTML = `
    <section class="stack">
      <div class="toolbar">
        <button data-action="back-to-quizzes" type="button">Back to Quizzes</button>
      </div>
      <div class="list">
        ${attempts
          .map(
            (a) => `
              <article class="card">
                <div class="card-header">
                  <div>
                    <div class="badge-row">
                      <span class="badge gold">${escapeHtml(a.quiz_type)}</span>
                      <span class="badge blue">${escapeHtml(a.percentage)}%</span>
                    </div>
                    <h2>${escapeHtml(a.quiz_title)}</h2>
                    <p class="muted">Score: ${escapeHtml(a.score)} / ${escapeHtml(a.total_points)} &middot; ${escapeHtml(a.question_count)} questions &middot; ${escapeHtml(a.seconds_spent)}s</p>
                  </div>
                  <button data-action="view-attempt" data-id="${a.id}" type="button">View</button>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

async function downloadDataset(dataset) {
  const response = await fetch(`/api/research/export/${dataset}`, {
    headers: { Authorization: `Bearer ${state.token}` },
  });
  if (!response.ok) {
    throw new Error("Could not export dataset.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${dataset}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showMessage(`${dataset.replaceAll("_", " ")} export downloaded.`);
}

async function boot() {
  if (!state.token) {
    document.querySelector("#boot-loader").classList.add("hidden");
    showLanding();
    return;
  }
  try {
    state.user = await api("/api/me");
    document.querySelector("#boot-loader").classList.add("hidden");
    showApp();
    await refreshAndRender();
    startNotificationPolling();
  } catch {
    clearSession();
    document.querySelector("#boot-loader").classList.add("hidden");
  }
}

boot();
