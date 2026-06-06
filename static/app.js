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
  quizTimeLeft: 70,
  quizResult: null,
  quizAttempts: [],
};

const authScreen = document.querySelector("#auth-screen");
const appScreen = document.querySelector("#app-screen");
const nav = document.querySelector("#nav");
const content = document.querySelector("#content");
const message = document.querySelector("#message");
const viewTitle = document.querySelector("#view-title");
const viewKicker = document.querySelector("#view-kicker");
const userName = document.querySelector("#user-name");

const navItems = [
  ["overview", "Overview"],
  ["courses", "Courses"],
  ["resources", "Resources"],
  ["discussions", "Discussions"],
  ["quizzes", "Quizzes"],
  ["reflections", "Reflections"],
  ["feedback", "Feedback"],
  ["research", "Research"],
];

function canResearch() {
  return state.user && ["researcher", "admin"].includes(state.user.role);
}

function canManageContent() {
  return state.user && ["facilitator", "researcher", "admin"].includes(state.user.role);
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
  message.textContent = text;
  message.className = `message ${type === "error" ? "error" : ""}`;
  window.setTimeout(() => message.classList.add("hidden"), 4500);
}

function showAuth() {
  authScreen.classList.remove("hidden");
  appScreen.classList.add("hidden");
}

function showApp() {
  authScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  userName.textContent = `${state.user.full_name} (${state.user.research_id})`;
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
    try {
      const error = await response.json();
      detail = error.detail || detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail);
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
  showAuth();
}

function setTitle(title, kicker = "Workspace") {
  viewTitle.textContent = title;
  viewKicker.textContent = kicker;
}

function renderNav() {
  nav.innerHTML = navItems
    .filter(([id]) => id !== "research" || canResearch())
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
  const [courses, resources, discussions, quizzes] = await Promise.all([
    api("/api/courses"),
    api("/api/resources"),
    api("/api/discussions?include_replies=false"),
    api("/api/quizzes"),
  ]);
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
  state.quizTimeLeft = 70;
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
  if (fill) fill.style.width = `${(state.quizTimeLeft / 70) * 100}%`;
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
  const discussionCount = state.discussions.length;
  const quizCount = state.quizzes.length;

  content.innerHTML = `
    <section class="grid">
      ${metric("Courses", courseCount)}
      ${metric("Learning Resources", resourceCount)}
      ${metric("Discussions", discussionCount)}
      ${metric("Assessments", quizCount)}
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

function renderResources() {
  setTitle("Resources", "Learning materials");
  const filtered = state.selectedCourse
    ? state.resources.filter((resource) => String(resource.course_id) === String(state.selectedCourse))
    : state.resources;

  content.innerHTML = `
    <section class="toolbar">
      <select id="course-filter">
        <option value="">All courses</option>
        ${courseOptions(state.selectedCourse)}
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
        <label>Course <select name="course_id">${courseOptions()}</select></label>
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
          <span class="timer-text">70s</span>
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
  if (state.view === "resources") renderResources();
  if (state.view === "discussions") renderDiscussions();
  if (state.view === "quizzes") renderQuizzes();
  if (state.view === "reflections") renderReflections();
  if (state.view === "feedback") renderFeedback();
  if (state.view === "research") await renderResearch();
}

async function refreshAndRender() {
  await loadCoreData();
  await render();
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
  try {
    const payload = formData(event.currentTarget);
    const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(payload) });
    saveSession(data);
    showApp();
    await refreshAndRender();
    showMessage("Signed in.");
  } catch (error) {
    showMessage(error.message, "error");
  }
});

document.querySelector("#register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = formData(event.currentTarget);
    payload.accepted_research_consent = event.currentTarget.accepted_research_consent.checked;
    const data = await api("/api/auth/register", { method: "POST", body: JSON.stringify(payload) });
    saveSession(data);
    showApp();
    await refreshAndRender();
    showMessage("Account created.");
  } catch (error) {
    showMessage(error.message, "error");
  }
});

document.querySelector("#logout-btn").addEventListener("click", clearSession);

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

content.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  const id = button.dataset.id;

  try {
    if (action === "join-course") {
      await api(`/api/courses/${id}/join`, { method: "POST", body: JSON.stringify({}) });
      await refreshAndRender();
      showMessage("Course joined.");
    }

    if (action === "view-resource") {
      await api(`/api/resources/${id}?seconds_spent=30`);
      await loadCoreData();
      renderResources();
      showMessage("Resource view recorded.");
    }

    if (action === "load-thread") {
      const discussions = await api("/api/discussions");
      state.discussions = discussions;
      renderDiscussions();
    }

    if (action === "helpful") {
      await api(`/api/replies/${id}/helpful`, { method: "POST" });
      const discussions = await api("/api/discussions");
      state.discussions = discussions;
      renderDiscussions();
      showMessage("Helpful vote recorded.");
    }

    if (action === "open-quiz") {
      const quiz = await api(`/api/quizzes/${id}`);
      state.activeQuiz = quiz;
      state.quizQuestions = quiz.questions || [];
      state.quizIndex = 0;
      state.quizAnswers = {};
      state.quizPhase = "active";
      state.quizStartedAt = Date.now();
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
      await loadCoreData();
      renderQuizList();
    }

    if (action === "export") {
      await downloadDataset(id);
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
      await refreshAndRender();
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
      await refreshAndRender();
      showMessage("Resource added.");
    }

    if (type === "create-discussion") {
      const payload = formData(form);
      payload.course_id = Number(payload.course_id);
      await api("/api/discussions", { method: "POST", body: JSON.stringify(payload) });
      form.reset();
      state.discussions = await api("/api/discussions");
      renderDiscussions();
      showMessage("Discussion posted.");
    }

    if (type === "reply") {
      await api(`/api/discussions/${form.dataset.id}/replies`, {
        method: "POST",
        body: JSON.stringify(formData(form)),
      });
      form.reset();
      state.discussions = await api("/api/discussions");
      renderDiscussions();
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
    showAuth();
    return;
  }
  try {
    state.user = await api("/api/me");
    showApp();
    await refreshAndRender();
  } catch {
    clearSession();
  }
}

boot();
