import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.course_banks import COURSE_QUESTION_BANK
from app.utils import hash_password, normalized_email
from db.database import engine
from model import (
    Course,
    PracticalExercise,
    Quiz,
    QuizQuestion,
    Resource,
    Survey,
    SurveyQuestion,
    User,
)


def ensure_seed_quiz(db: Session, course: Course, title: str, description: str) -> Quiz:
    existing = db.scalar(select(Quiz).where(Quiz.course_id == course.id, Quiz.quiz_type == "test"))
    if existing:
        existing.title = title
        existing.description = description
        return existing

    reusable = db.scalar(
        select(Quiz)
        .where(Quiz.course_id == course.id, Quiz.quiz_type.in_(["practice", "pretest", "posttest"]))
        .order_by(Quiz.quiz_type == "practice")
    )
    if reusable:
        reusable.title = title
        reusable.quiz_type = "test"
        reusable.description = description
        return reusable

    quiz = Quiz(course_id=course.id, title=title, quiz_type="test", description=description)
    db.add(quiz)
    db.flush()
    return quiz


def ensure_seed_questions(db: Session, quiz: Quiz, questions: list[dict]) -> None:
    existing_count = len(quiz.questions)
    if existing_count >= len(questions):
        return
    for question_data in questions[existing_count:]:
        db.add(QuizQuestion(quiz_id=quiz.id, **question_data))
    db.flush()


def seed_quiz_banks(db: Session, courses_by_code: dict[str, Course]) -> None:
    for code, bank in COURSE_QUESTION_BANK.items():
        course = courses_by_code.get(code)
        if course is None:
            continue

        test = ensure_seed_quiz(
            db,
            course,
            f"{course.title} Test",
            "Rotating assessment drawn from a larger course question bank. Each attempt receives a fresh question round.",
        )
        ensure_seed_questions(db, test, bank)
        archive_legacy_quizzes(db, course, test.id)


def archive_legacy_quizzes(db: Session, course: Course, active_quiz_id: int) -> None:
    legacy_quizzes = db.scalars(
        select(Quiz).where(
            Quiz.course_id == course.id,
            Quiz.id != active_quiz_id,
            Quiz.quiz_type.in_(["pretest", "practice", "posttest"]),
        )
    ).all()
    for quiz in legacy_quizzes:
        if quiz.attempts:
            quiz.quiz_type = "archived"
            quiz.title = f"Archived - {quiz.title}"
        else:
            db.delete(quiz)


PRACTICAL_EXERCISE_SEEDS = [
    {
        "course_code": "COSC101",
        "title": "Python Basics: Student Summary",
        "practical_type": "python",
        "difficulty": "beginner",
        "prompt": "Write a Python function named student_summary(name, level) that returns a readable sentence containing both values.",
        "starter_code": "def student_summary(name, level):\n    # return a sentence using name and level\n    pass",
        "expected_output": "student_summary('Amina', '200 Level') returns a sentence containing Amina and 200 Level.",
        "solution_notes": "Use a function definition, parameters, and string formatting or concatenation to build the sentence.",
        "checks": [
            {"label": "Defines student_summary", "contains_all": ["def student_summary"]},
            {"label": "Uses both parameters", "contains_all": ["name", "level"]},
            {"label": "Returns a value", "contains_all": ["return"]},
        ],
    },
    {
        "course_code": "COSC211",
        "title": "Java Methods: Average Score",
        "practical_type": "java",
        "difficulty": "beginner",
        "prompt": "Create a Java method named averageScore that receives three integer scores and returns their average as a double.",
        "starter_code": "public class Practice {\n    public static double averageScore(int a, int b, int c) {\n        // return the average as a double\n        return 0;\n    }\n}",
        "expected_output": "averageScore(60, 75, 90) should return 75.0.",
        "solution_notes": "Use a double calculation such as (a + b + c) / 3.0 so integer division does not lose decimals.",
        "checks": [
            {"label": "Defines averageScore", "contains_all": ["averageScore", "double"]},
            {"label": "Accepts three integer inputs", "contains_all": ["int a", "int b", "int c"]},
            {"label": "Avoids integer division", "contains_any": ["/ 3.0", "/3.0", "(double)"]},
        ],
    },
    {
        "course_code": "COSC212",
        "title": "Java OOP: Course Class",
        "practical_type": "java",
        "difficulty": "intermediate",
        "prompt": "Define a Course class with private code and title fields, a constructor, and a getDisplayName method that combines both fields.",
        "starter_code": "public class Course {\n    // private fields\n\n    public Course(String code, String title) {\n    }\n\n    public String getDisplayName() {\n        return \"\";\n    }\n}",
        "expected_output": "new Course('COSC211', 'OOP').getDisplayName() should include COSC211 and OOP.",
        "solution_notes": "Encapsulate fields with private access and assign constructor parameters using this.code and this.title.",
        "checks": [
            {"label": "Uses private fields", "contains_all": ["private String code", "private String title"]},
            {"label": "Defines constructor", "contains_all": ["public Course", "this.code", "this.title"]},
            {"label": "Returns display text", "contains_all": ["getDisplayName", "return"]},
        ],
    },
    {
        "course_code": "COSC301",
        "title": "Python Data Structures: Stack",
        "practical_type": "python",
        "difficulty": "intermediate",
        "prompt": "Implement push_item(stack, item) and pop_item(stack) using a Python list as a stack.",
        "starter_code": "def push_item(stack, item):\n    pass\n\n\ndef pop_item(stack):\n    pass",
        "expected_output": "push_item should append to the list; pop_item should remove and return the most recent item.",
        "solution_notes": "A stack is last-in, first-out. Python list append and pop are enough for this exercise.",
        "checks": [
            {"label": "Defines push_item", "contains_all": ["def push_item"]},
            {"label": "Uses append for push", "contains_all": [".append("]},
            {"label": "Uses pop for removal", "contains_all": [".pop("]},
        ],
    },
    {
        "course_code": "COSC307",
        "title": "Python Web Helper: Validate Email",
        "practical_type": "python",
        "difficulty": "beginner",
        "prompt": "Write a function is_valid_email(email) that returns True only when the text contains @ and a dot after @.",
        "starter_code": "def is_valid_email(email):\n    pass",
        "expected_output": "is_valid_email('student@abu.edu.ng') should return True; is_valid_email('student') should return False.",
        "solution_notes": "Check for @, split the domain portion, and confirm the domain includes a dot.",
        "checks": [
            {"label": "Defines is_valid_email", "contains_all": ["def is_valid_email"]},
            {"label": "Checks for @", "contains_all": ["@"]},
            {"label": "Returns booleans", "contains_any": ["True", "False"]},
        ],
    },
    {
        "course_code": "COSC309",
        "title": "SQL Select: High Scoring Students",
        "practical_type": "database",
        "difficulty": "beginner",
        "prompt": "Write an SQL query that selects student names and scores from a results table where score is at least 70, ordered from highest score to lowest.",
        "starter_code": "SELECT \nFROM results\nWHERE \nORDER BY ;",
        "expected_output": "The query should return name and score columns for rows with score >= 70 in descending score order.",
        "solution_notes": "Use SELECT name, score, WHERE score >= 70, and ORDER BY score DESC.",
        "checks": [
            {"label": "Selects name and score", "contains_all": ["select", "name", "score"], "case_sensitive": False},
            {"label": "Filters by score", "contains_any": ["score >= 70", "score>=70"], "case_sensitive": False},
            {"label": "Orders descending", "contains_all": ["order by", "desc"], "case_sensitive": False},
        ],
    },
    {
        "course_code": "COSC406",
        "title": "SQL Join: Course Enrolment",
        "practical_type": "database",
        "difficulty": "intermediate",
        "prompt": "Write an SQL query that returns each student's name with the course code they enrolled in using students, enrolments, and courses tables.",
        "starter_code": "SELECT \nFROM students\nJOIN enrolments ON \nJOIN courses ON ;",
        "expected_output": "Rows should include student name and course code from joined tables.",
        "solution_notes": "Join students to enrolments by student id, then join courses by course id.",
        "checks": [
            {"label": "Uses joins", "contains_all": ["join enrolments", "join courses"], "case_sensitive": False},
            {"label": "Returns student name", "contains_all": ["name"], "case_sensitive": False},
            {"label": "Returns course code", "contains_all": ["code"], "case_sensitive": False},
        ],
    },
    {
        "course_code": "COSC401",
        "title": "Python Algorithms: Linear Search",
        "practical_type": "python",
        "difficulty": "intermediate",
        "prompt": "Write linear_search(values, target) that returns the index of target in values, or -1 when target is absent.",
        "starter_code": "def linear_search(values, target):\n    pass",
        "expected_output": "linear_search([4, 8, 10], 8) should return 1; missing values should return -1.",
        "solution_notes": "Loop through the list with indexes and compare each value with target.",
        "checks": [
            {"label": "Defines linear_search", "contains_all": ["def linear_search"]},
            {"label": "Loops through values", "contains_any": ["for ", "while "]},
            {"label": "Handles not found", "contains_all": ["-1"]},
        ],
    },
]


def seed_practical_exercises(db: Session, courses_by_code: dict[str, Course]) -> None:
    existing = {
        (exercise.course_id, exercise.title)
        for exercise in db.scalars(select(PracticalExercise)).all()
    }
    for item in PRACTICAL_EXERCISE_SEEDS:
        course = courses_by_code.get(item["course_code"])
        if course is None or (course.id, item["title"]) in existing:
            continue
        db.add(
            PracticalExercise(
                course_id=course.id,
                title=item["title"],
                practical_type=item["practical_type"],
                difficulty=item["difficulty"],
                prompt=item["prompt"],
                starter_code=item["starter_code"],
                expected_output=item["expected_output"],
                solution_notes=item["solution_notes"],
                checks_json=json.dumps(item["checks"]),
            )
        )


def seed_database(db: Session) -> None:
    researcher_email = normalized_email(
        "researcher@abuzaria.edu.ng"
    )
    researcher_password = "cop@12345678"

    researcher = db.scalar(select(User).where(User.email == researcher_email))
    if researcher is None:
        researcher = User(
            research_id="ABU-CS-RESEARCHER",
            full_name="ABU Zaria Researcher",
            email=researcher_email,
            password_hash=hash_password(researcher_password),
            role="researcher",
            study_group="experimental",
            programme="Computer Science Education",
            department="Science Education",
            level="Research",
            interests="Community of practice analytics",
        )
        db.add(researcher)
        db.flush()

    admin_email = normalized_email("copadmin@gmail.com")
    admin_password = "copadminadmin"
    admin = db.scalar(select(User).where(User.email == admin_email))
    if admin is None:
        admin = User(
            research_id="ABU-CS-ADMIN",
            full_name="COP Admin",
            email=admin_email,
            password_hash=hash_password(admin_password),
            role="admin",
            study_group="experimental",
            programme="Computer Science Education",
            department="Science Education",
            level="Research",
            interests="Platform administration",
        )
        db.add(admin)
        db.flush()

    if db.scalar(select(func.count(Course.id))) == 0:
        courses = [
            Course(
                title="Introduction To Computing",
                code="COSC101",
                description="Computer systems, hardware components, operating systems, office applications, and internet tools.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Object-Oriented Programming I",
                code="COSC211",
                description="Introduction to object-orientation, data types, control structures, arrays, recursion, and inheritance.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Data Structures and Algorithm",
                code="COSC301",
                description="Big-O analysis, stacks, queues, lists, trees, graphs, hash tables, and algorithm design strategies.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Database Management Systems",
                code="COSC309",
                description="Conceptual modeling, relational theory, SQL, normalization, security, query processing, and transactions.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Web Applications Engineering I",
                code="COSC307",
                description="Web architecture, XHTML, CSS, JavaScript, DOM, client-server interaction, and multimedia integration.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Operating Systems",
                code="COSC411",
                description="Process management, CPU scheduling, memory and virtual memory, file systems, I/O, and security.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Discrete Structures",
                code="COSC203",
                description="Functions, relations, counting, graphs, trees, discrete probability, and recurrence relations.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Organization and Assembly Language",
                code="COSC204",
                description="Computer organization, number representation, assembly programming, addressing modes, and interrupts.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Digital Logic Design",
                code="COSC205",
                description="Boolean algebra, combinational and sequential circuits, flip-flops, multiplexers, and memory elements.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Human Computer Interaction",
                code="COSC206",
                description="HCI foundations, GUI principles, usability evaluation, user-centered design, and interaction design.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Introduction to Artificial Intelligence",
                code="COSC208",
                description="Problem-solving, knowledge representation, expert systems, natural language processing, and machine learning.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Object-Oriented Programming II",
                code="COSC212",
                description="Advanced OOP, polymorphism, interfaces, packages, API usage, recursion, and event-driven programming.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Computer Architecture",
                code="COSC303",
                description="Memory hierarchy, cache, pipelining, superscalar architecture, RISC, and parallel architectures.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Systems Analysis and Design",
                code="COSC305",
                description="SDLC, UML modelling, use cases, sequence diagrams, class diagrams, CASE tools, and project management.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Organization of Programming Languages",
                code="COSC311",
                description="Syntax and semantics, data types, control structures, subprograms, exception handling, and programming paradigms.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Research Project in Computer Science Education",
                code="SECS403",
                description="Research design, methodology, data collection, analysis, and reporting in CS education research.",
                facilitator="Research Project Supervisor",
            ),
            Course(
                title="Algorithms and Complexity Analysis",
                code="COSC401",
                description="Algorithm analysis, divide-and-conquer, greedy algorithms, dynamic programming, NP-completeness.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Formal Methods in Software Development",
                code="COSC402",
                description="Z notation, Hoare logic, BNF, model checking, finite state machines, temporal logic, and verification.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Software Engineering",
                code="COSC403",
                description="Design patterns, coupling, cohesion, MVC, refactoring, UML, information hiding, and software process models.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Network Design and Management",
                code="COSC404",
                description="Network design methodologies, SNMP, RMON, MIB, fault management, configuration management, and NOC operations.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Web Applications Engineering II",
                code="COSC405",
                description="Server-side development, session management, input validation, cookies, database integration, and web security.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Advanced Database Systems",
                code="COSC406",
                description="Concurrency control, distributed databases, CAP theorem, object-oriented databases, query optimisation, and recovery.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Data Communications and Networks",
                code="COSC407",
                description="OSI model, TCP/IP, routing, DNS, Ethernet, subnetting, network topologies, and data link protocols.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Compiler Construction",
                code="COSC408",
                description="Lexical analysis, parsing, semantic analysis, symbol tables, intermediate code, optimisation, and code generation.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Professional and Social Aspects of Computing",
                code="COSC409",
                description="Professional ethics, intellectual property, data protection, computer crime, privacy, and social impact of IT.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Computational Science and Numerical Methods",
                code="COSC413",
                description="High-performance computing, parallel programming, scientific visualization, GPU computing, and numerical methods.",
                facilitator="Computer Science Facilitator",
            ),
            Course(
                title="Simulation Methodology",
                code="COSC416",
                description="Discrete-event simulation, random number generation, queuing theory, GPSS, output analysis, and model validation.",
                facilitator="Computer Science Facilitator",
            ),
        ]
        db.add_all(courses)
        db.flush()

    courses_by_code = {course.code: course for course in db.scalars(select(Course)).all()}

    if db.scalar(select(func.count(Resource.id))) == 0:
        resources = [
            Resource(course_id=courses_by_code["COSC101"].id, created_by_id=researcher.id, title="Introduction to Computers - Full Course", resource_type="video", difficulty="beginner", estimated_minutes=60, video_url="https://www.youtube.com/watch?v=y2kg3MO2WeI", blog_url="https://edu.gcfglobal.org/en/computerbasics/", body="Complete beginner-friendly video covering hardware, software, operating systems, and how computers work. Start here if you are new to computing."),
            Resource(course_id=courses_by_code["COSC101"].id, created_by_id=researcher.id, title="Computer Basics - Reading Guide", resource_type="blog", difficulty="beginner", estimated_minutes=20, url="https://www.tutorialspoint.com/computer_fundamentals/index.htm", blog_url="https://edu.gcfglobal.org/en/computerbasics/", body="Text-based tutorial covering input/output devices, system units, storage, and basic troubleshooting."),
            Resource(course_id=courses_by_code["COSC211"].id, created_by_id=researcher.id, title="Java Programming for Beginners - freeCodeCamp", resource_type="video", difficulty="beginner", estimated_minutes=120, video_url="https://www.youtube.com/watch?v=A74TOX803D0", blog_url="https://www.geeksforgeeks.org/java/", body="A 4-hour freeCodeCamp Java tutorial covering data types, control flow, OOP basics, arrays, and exception handling."),
            Resource(course_id=courses_by_code["COSC211"].id, created_by_id=researcher.id, title="Object-Oriented Programming Concepts Explained", resource_type="blog", difficulty="beginner", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/object-oriented-programming-oops-concept-in-java/", video_url="https://www.youtube.com/watch?v=pTB0EiLXUC8", body="Clear explanation of encapsulation, inheritance, polymorphism, and abstraction with Java examples."),
            Resource(course_id=courses_by_code["COSC301"].id, created_by_id=researcher.id, title="Data Structures - CS Dojo Playlist", resource_type="video", difficulty="intermediate", estimated_minutes=90, video_url="https://www.youtube.com/playlist?list=PLBZBJbE_rGRV8D7XZ08LK6z-4zPoWzu5H", blog_url="https://www.geeksforgeeks.org/data-structures/", body="Visual and beginner-friendly explanations of arrays, linked lists, stacks, queues, trees, and hash tables."),
            Resource(course_id=courses_by_code["COSC301"].id, created_by_id=researcher.id, title="Big-O Notation & Algorithm Analysis", resource_type="blog", difficulty="intermediate", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/analysis-of-algorithms-set-1-asymptotic-analysis/", video_url="https://www.youtube.com/watch?v=D6xkbGLQesk", body="Learn how to analyze algorithm efficiency using Big-O notation with practical examples."),
            Resource(course_id=courses_by_code["COSC309"].id, created_by_id=researcher.id, title="SQL Tutorial - Full Database Course for Beginners", resource_type="video", difficulty="beginner", estimated_minutes=90, video_url="https://www.youtube.com/watch?v=HXV3zeQKqGY", blog_url="https://www.w3schools.com/sql/", body="Complete freeCodeCamp SQL tutorial covering SELECT, JOINs, aggregation, subqueries, and database design."),
            Resource(course_id=courses_by_code["COSC309"].id, created_by_id=researcher.id, title="Database Normalization Explained (1NF, 2NF, 3NF, BCNF)", resource_type="blog", difficulty="intermediate", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/normal-forms-in-dbms/", video_url="https://www.youtube.com/watch?v=GFQaEYEc8_8", body="Step-by-step guide to database normalization with examples. Covers First through Third Normal Form and BCNF."),
            Resource(course_id=courses_by_code["COSC309"].id, created_by_id=researcher.id, title="DBMS Notes - Complete Reference", resource_type="reference", difficulty="intermediate", estimated_minutes=30, url="https://www.javatpoint.com/dbms-tutorial", blog_url="https://www.tutorialspoint.com/dbms/index.htm", body="Comprehensive DBMS tutorial covering ER models, relational algebra, SQL, normalization, transactions, and concurrency control."),
            Resource(course_id=courses_by_code["COSC307"].id, created_by_id=researcher.id, title="HTML & CSS Full Course", resource_type="video", difficulty="beginner", estimated_minutes=120, video_url="https://www.youtube.com/watch?v=G3e-cpL7ofc", blog_url="https://developer.mozilla.org/en-US/docs/Learn/HTML", body="Complete HTML and CSS tutorial from SuperSimpleDev covering structure, styling, layouts, and responsive design."),
            Resource(course_id=courses_by_code["COSC307"].id, created_by_id=researcher.id, title="JavaScript DOM Manipulation Guide", resource_type="blog", difficulty="intermediate", estimated_minutes=25, blog_url="https://www.geeksforgeeks.org/dom-document-object-model/", video_url="https://www.youtube.com/watch?v=5fb2aPlgoys", body="Learn how to use JavaScript to manipulate web page content, handle events, and build interactive UIs."),
            Resource(course_id=courses_by_code["COSC411"].id, created_by_id=researcher.id, title="Operating Systems - Neso Academy Playlist", resource_type="video", difficulty="intermediate", estimated_minutes=180, video_url="https://www.youtube.com/playlist?list=PLBlnK6fEyqRiVhbXDGLXDk_OQAeuVcp2O", blog_url="https://www.geeksforgeeks.org/operating-systems/", body="Comprehensive OS playlist covering processes, CPU scheduling, memory management, virtual memory, and file systems."),
            Resource(course_id=courses_by_code["COSC411"].id, created_by_id=researcher.id, title="Process Management & Scheduling Algorithms", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/cpu-scheduling-in-operating-systems/", video_url="https://www.youtube.com/watch?v=MZdVAVMgNpA", body="Detailed breakdown of FCFS, SJF, Priority, and Round Robin scheduling algorithms with worked examples."),
            Resource(course_id=courses_by_code["COSC203"].id, created_by_id=researcher.id, title="Discrete Mathematics - TrevTutor Playlist", resource_type="video", difficulty="intermediate", estimated_minutes=120, video_url="https://www.youtube.com/playlist?list=PLDDGPdw7e6Ag1EIznZ-m-qXu4XX3A0cIz", blog_url="https://www.geeksforgeeks.org/discrete-mathematics-tutorial/", body="Video series covering logic, sets, functions, relations, counting, graph theory, and recurrence relations."),
            Resource(course_id=courses_by_code["COSC203"].id, created_by_id=researcher.id, title="Graph Theory Fundamentals", resource_type="blog", difficulty="intermediate", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/graph-theory-tutorial/", video_url="https://www.youtube.com/watch?v=LFKZLXVO-Dg", body="Introduction to graph types, representations, traversals, trees, and their applications in computer science."),
            Resource(course_id=courses_by_code["COSC204"].id, created_by_id=researcher.id, title="Assembly Language Programming - Tutorial", resource_type="video", difficulty="intermediate", estimated_minutes=90, video_url="https://www.youtube.com/playlist?list=PLKK11LigqithKp_Y0A1kh_29YuoF1W5WA", blog_url="https://www.tutorialspoint.com/assembly_programming/index.htm", body="Assembly language programming tutorial covering registers, addressing modes, instructions, and program structure."),
            Resource(course_id=courses_by_code["COSC204"].id, created_by_id=researcher.id, title="Number Systems & Data Representation", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/number-system-and-base-conversions/", video_url="https://www.youtube.com/watch?v=LpuPe81bc2w", body="Binary, octal, hexadecimal number systems and how computers represent integers, floating-point, and characters."),
            Resource(course_id=courses_by_code["COSC205"].id, created_by_id=researcher.id, title="Digital Logic - Neso Academy Playlist", resource_type="video", difficulty="intermediate", estimated_minutes=120, video_url="https://www.youtube.com/playlist?list=PLBlnK6fEyqRjMH3mWf6klqiB7d0cO1sOX", blog_url="https://www.geeksforgeeks.org/digital-electronics-logic-design-tutorials/", body="Complete digital logic design course covering Boolean algebra, logic gates, K-maps, combinational and sequential circuits."),
            Resource(course_id=courses_by_code["COSC205"].id, created_by_id=researcher.id, title="Karnaugh Maps (K-Maps) Explained", resource_type="blog", difficulty="intermediate", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/introduction-of-k-map-karnaugh-map/", video_url="https://www.youtube.com/watch?v=RO5alU6PpSU", body="Step-by-step guide to simplifying Boolean expressions using K-Maps with 2, 3, and 4 variable examples."),
            Resource(course_id=courses_by_code["COSC206"].id, created_by_id=researcher.id, title="Human-Computer Interaction - Course Intro", resource_type="video", difficulty="intermediate", estimated_minutes=60, video_url="https://www.youtube.com/playlist?list=PLVHgdkG5gPpgrJ7IUjjYKq8cf6PNKFWaR", blog_url="https://www.interaction-design.org/literature/topics/human-computer-interaction", body="Introduction to HCI principles, usability heuristics, user-centered design, and interface evaluation methods."),
            Resource(course_id=courses_by_code["COSC206"].id, created_by_id=researcher.id, title="Usability Heuristics - Nielsen's 10 Principles", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://www.nngroup.com/articles/ten-usability-heuristics/", video_url="https://www.youtube.com/watch?v=6B-NM9HM8bI", body="Jakob Nielsen's 10 usability heuristics with real-world examples and how to apply them in interface design."),
            Resource(course_id=courses_by_code["COSC208"].id, created_by_id=researcher.id, title="Artificial Intelligence - Free Course", resource_type="video", difficulty="intermediate", estimated_minutes=120, video_url="https://www.youtube.com/playlist?list=PLBlnK6fEyqRgjSOSTcfxFJPLQW0_BFeSC", blog_url="https://www.geeksforgeeks.org/artificial-intelligence-an-introduction/", body="Comprehensive AI playlist covering search algorithms, knowledge representation, expert systems, and machine learning basics."),
            Resource(course_id=courses_by_code["COSC208"].id, created_by_id=researcher.id, title="Machine Learning - Andrew Ng Course Notes", resource_type="blog", difficulty="intermediate", estimated_minutes=30, blog_url="https://www.geeksforgeeks.org/machine-learning/", video_url="https://www.youtube.com/playlist?list=PLoROMvodv4rMiGQp3WXShtMGgzqpfVfbU", body="Stanford's famous ML course covering supervised learning, neural networks, and practical ML methodology."),
            Resource(course_id=courses_by_code["COSC212"].id, created_by_id=researcher.id, title="Advanced Java & OOP - Coding with John", resource_type="video", difficulty="intermediate", estimated_minutes=90, video_url="https://www.youtube.com/playlist?list=PLqq-6Pq4lTTaV40RcNkPqFIh0S9_JhC-B", blog_url="https://www.geeksforgeeks.org/java/", body="Deep dive into polymorphism, interfaces, abstract classes, generics, collections framework, and design patterns."),
            Resource(course_id=courses_by_code["COSC212"].id, created_by_id=researcher.id, title="Java Design Patterns Explained", resource_type="blog", difficulty="advanced", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/software-design-patterns/", video_url="https://www.youtube.com/watch?v=tv-_1er1mWI", body="Overview of creational, structural, and behavioral design patterns with Java implementations and real-world use cases."),
            Resource(course_id=courses_by_code["COSC303"].id, created_by_id=researcher.id, title="Computer Architecture - Carnegie Mellon Course", resource_type="video", difficulty="advanced", estimated_minutes=120, video_url="https://www.youtube.com/playlist?list=PL5PHm2jkkXmi5CxxI7b3JCL1HvKZ5J0Wq", blog_url="https://www.geeksforgeeks.org/computer-organization-and-architecture-tutorials/", body="University-level computer architecture lectures covering pipelining, cache design, instruction-level parallelism, and memory hierarchy."),
            Resource(course_id=courses_by_code["COSC303"].id, created_by_id=researcher.id, title="Cache Memory & Memory Hierarchy", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/cache-memory-in-computer-organization/", video_url="https://www.youtube.com/watch?v=yi0FhRqDJfo", body="Understanding how cache memory works, mapping techniques (direct, associative, set-associative), and performance analysis."),
            Resource(course_id=courses_by_code["COSC305"].id, created_by_id=researcher.id, title="UML Diagrams - Complete Tutorial", resource_type="video", difficulty="intermediate", estimated_minutes=60, video_url="https://www.youtube.com/playlist?list=PLWPirh4EWFpFU1__BKbXHqV3N_7GJxN0t", blog_url="https://www.geeksforgeeks.org/unified-modeling-language-uml-introduction/", body="Complete guide to UML: use case diagrams, class diagrams, sequence diagrams, activity diagrams, and state charts."),
            Resource(course_id=courses_by_code["COSC305"].id, created_by_id=researcher.id, title="SDLC Methodologies Compared", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/software-development-life-cycle-sdlc/", video_url="https://www.youtube.com/watch?v=i-QyW8D3ei0", body="Comparison of Waterfall, Agile, Scrum, and DevOps methodologies with pros/cons and when to use each approach."),
            Resource(course_id=courses_by_code["COSC311"].id, created_by_id=researcher.id, title="Programming Paradigms Explained", resource_type="video", difficulty="intermediate", estimated_minutes=30, video_url="https://www.youtube.com/watch?v=3TBq__oKUzk", blog_url="https://www.geeksforgeeks.org/introduction-of-programming-paradigms/", body="Clear explanation of imperative, object-oriented, functional, and logic programming paradigms with examples in multiple languages."),
            Resource(course_id=courses_by_code["COSC311"].id, created_by_id=researcher.id, title="Programming Language Concepts - Reference Guide", resource_type="reference", difficulty="intermediate", estimated_minutes=25, url="https://www.tutorialspoint.com/compiler_design/index.htm", blog_url="https://www.geeksforgeeks.org/introduction-of-programming-paradigms/", body="Covers syntax and semantics, data types, control structures, subprograms, exception handling, and type systems across languages."),
            Resource(course_id=courses_by_code["COSC401"].id, created_by_id=researcher.id, title="Algorithms - MIT OpenCourseWare", resource_type="video", difficulty="advanced", estimated_minutes=180, video_url="https://www.youtube.com/playlist?list=PLUl4u3cNGP63EdVPNLG3ToM6LaEUuStmh", blog_url="https://www.geeksforgeeks.org/fundamentals-of-algorithms/", body="MIT 6.006 Introduction to Algorithms lectures covering divide-and-conquer, dynamic programming, greedy algorithms, and NP-completeness."),
            Resource(course_id=courses_by_code["COSC401"].id, created_by_id=researcher.id, title="Dynamic Programming - Practice Guide", resource_type="blog", difficulty="advanced", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/dynamic-programming/", video_url="https://www.youtube.com/watch?v=oBt53YbR9Kk", body="Learn DP strategies with worked examples: memoization, tabulation, knapsack, LCS, and matrix chain multiplication."),
            Resource(course_id=courses_by_code["COSC402"].id, created_by_id=researcher.id, title="Formal Methods & Logic in CS", resource_type="video", difficulty="advanced", estimated_minutes=90, video_url="https://www.youtube.com/playlist?list=PLlGpxZfYuK8LqUsRGZRc0HDZdoogKFW9G", blog_url="https://www.geeksforgeeks.org/introduction-of-formal-methods/", body="Introduction to formal specification, Z notation, Hoare logic, model checking, and verification techniques for software."),
            Resource(course_id=courses_by_code["COSC402"].id, created_by_id=researcher.id, title="Finite State Machines & Model Checking", resource_type="blog", difficulty="advanced", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/introduction-of-finite-automata/", video_url="https://www.youtube.com/watch?v=Qa6csfkK7_I", body="Understanding FSMs, temporal logic, and how model checking verifies system properties against specifications."),
            Resource(course_id=courses_by_code["COSC403"].id, created_by_id=researcher.id, title="Software Engineering - Full Course", resource_type="video", difficulty="intermediate", estimated_minutes=120, video_url="https://www.youtube.com/playlist?list=PLBlnK6fEyqRhP4UEr7RYwzLlEVpG2Vp9o", blog_url="https://www.geeksforgeeks.org/software-engineering/", body="Comprehensive software engineering course: requirements, design patterns, testing, project management, and agile methodologies."),
            Resource(course_id=courses_by_code["COSC403"].id, created_by_id=researcher.id, title="Design Patterns - The Gang of Four", resource_type="blog", difficulty="intermediate", estimated_minutes=20, blog_url="https://refactoring.guru/design-patterns", video_url="https://www.youtube.com/watch?v=tv-_1er1mWI", body="Illustrated guide to the 23 classic GoF design patterns with UML diagrams, code examples, and real-world applications."),
            Resource(course_id=courses_by_code["COSC404"].id, created_by_id=researcher.id, title="Network Design & Management Fundamentals", resource_type="video", difficulty="advanced", estimated_minutes=90, video_url="https://www.youtube.com/playlist?list=PLBlnK6fEyqRgMCUAG0HRw3UAxq5CAEEmS", blog_url="https://www.geeksforgeeks.org/computer-network-tutorials/", body="Network design methodologies, SNMP, RMON, MIB, fault and configuration management, and NOC operations explained."),
            Resource(course_id=courses_by_code["COSC404"].id, created_by_id=researcher.id, title="Network Management Protocols - SNMP Deep Dive", resource_type="blog", difficulty="advanced", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/simple-network-management-protocol-snmp/", video_url="https://www.youtube.com/watch?v=7qB7e0LwYpQ", body="How SNMP v1/v2/v3 works, MIB structure, traps vs polling, and practical network monitoring with real examples."),
            Resource(course_id=courses_by_code["COSC405"].id, created_by_id=researcher.id, title="Backend Web Development - Node.js Course", resource_type="video", difficulty="intermediate", estimated_minutes=120, video_url="https://www.youtube.com/watch?v=Oe421EPjeBE", blog_url="https://developer.mozilla.org/en-US/docs/Learn/Server-side/First_steps", body="Complete backend development course covering server-side JavaScript, REST APIs, databases, authentication, and deployment."),
            Resource(course_id=courses_by_code["COSC405"].id, created_by_id=researcher.id, title="Web Security Best Practices", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://developer.mozilla.org/en-US/docs/Web/Security", video_url="https://www.youtube.com/watch?v=1rF7bR5XQGo", body="OWASP Top 10, XSS, CSRF, SQL injection prevention, secure session management, and input validation techniques."),
            Resource(course_id=courses_by_code["COSC406"].id, created_by_id=researcher.id, title="Advanced Databases - CMU Course", resource_type="video", difficulty="advanced", estimated_minutes=180, video_url="https://www.youtube.com/playlist?list=PLSE8ODhjZXjbj8BMuIrRcacnQh20hmY9g", blog_url="https://www.geeksforgeeks.org/dbms/", body="CMU 15-445 Advanced Database Systems: query optimization, concurrency control, distributed databases, and CAP theorem."),
            Resource(course_id=courses_by_code["COSC406"].id, created_by_id=researcher.id, title="Concurrency Control Protocols Explained", resource_type="blog", difficulty="advanced", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/concurrency-control-in-dbms/", video_url="https://www.youtube.com/watch?v=ZxVO1ORNKgE", body="Two-phase locking, timestamp ordering, optimistic concurrency control, and multi-version concurrency control (MVCC) with examples."),
            Resource(course_id=courses_by_code["COSC407"].id, created_by_id=researcher.id, title="Computer Networking - Full Course", resource_type="video", difficulty="intermediate", estimated_minutes=150, video_url="https://www.youtube.com/playlist?list=PLBlnK6fEyqRgMCUAG0HRw3UAxq5CAEEmS", blog_url="https://www.geeksforgeeks.org/computer-network-tutorials/", body="Complete networking course: OSI model, TCP/IP, routing protocols, DNS, subnetting, and Ethernet fundamentals."),
            Resource(course_id=courses_by_code["COSC407"].id, created_by_id=researcher.id, title="TCP/IP and the OSI Model Explained", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/layers-of-osi-model/", video_url="https://www.youtube.com/watch?v=vv4y_uOneC0", body="Layer-by-layer breakdown of the OSI model with real-world protocol examples and comparison to TCP/IP stack."),
            Resource(course_id=courses_by_code["COSC408"].id, created_by_id=researcher.id, title="Compiler Design - Neso Academy", resource_type="video", difficulty="advanced", estimated_minutes=120, video_url="https://www.youtube.com/playlist?list=PLBlnK6fEyqRjT3oJxFXRgjPNzeS-LFY-q", blog_url="https://www.geeksforgeeks.org/compiler-design-tutorials/", body="Complete compiler design playlist: lexical analysis, parsing (LL, LR), semantic analysis, code generation, and optimization."),
            Resource(course_id=courses_by_code["COSC408"].id, created_by_id=researcher.id, title="Build Your Own Interpreter - Crafting Interpreters", resource_type="blog", difficulty="advanced", estimated_minutes=30, blog_url="https://craftinginterpreters.com/contents.html", video_url="https://www.youtube.com/watch?v=4m7msrdLPMs", body="Free online book walking through building a complete interpreter and compiler from scratch in Java and C."),
            Resource(course_id=courses_by_code["COSC409"].id, created_by_id=researcher.id, title="Computer Ethics & Professional Responsibility", resource_type="video", difficulty="intermediate", estimated_minutes=45, video_url="https://www.youtube.com/watch?v=oFfWwNlwX-4", blog_url="https://www.geeksforgeeks.org/professional-ethics-in-computing/", body="Discussion of ACM Code of Ethics, intellectual property, data privacy, computer crime, and social impact of technology."),
            Resource(course_id=courses_by_code["COSC409"].id, created_by_id=researcher.id, title="Data Protection & Privacy Laws Overview", resource_type="blog", difficulty="intermediate", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/what-is-data-privacy/", video_url="https://www.youtube.com/watch?v=iVoy4lMr6iI", body="Overview of GDPR, NDPR (Nigeria), data subject rights, consent requirements, and how they affect software development."),
            Resource(course_id=courses_by_code["COSC413"].id, created_by_id=researcher.id, title="Parallel Programming with MPI & OpenMP", resource_type="video", difficulty="advanced", estimated_minutes=90, video_url="https://www.youtube.com/playlist?list=PLmJwSK7qduaULeFqBuowvMJkHjGUkcT5u", blog_url="https://www.geeksforgeeks.org/introduction-to-parallel-computing/", body="Introduction to parallel computing: MPI message passing, OpenMP shared memory, GPU computing concepts, and numerical methods."),
            Resource(course_id=courses_by_code["COSC413"].id, created_by_id=researcher.id, title="High-Performance Computing Fundamentals", resource_type="blog", difficulty="advanced", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/what-is-parallel-computing/", video_url="https://www.youtube.com/watch?v=7BqBoeH0KpQ", body="HPC architecture overview: clusters, supercomputers, scientific visualization, and performance optimization techniques."),
            Resource(course_id=courses_by_code["COSC416"].id, created_by_id=researcher.id, title="Simulation & Modeling - Full Course", resource_type="video", difficulty="advanced", estimated_minutes=90, video_url="https://www.youtube.com/playlist?list=PLbMVogVj5nJTHjJ31Hv1LLK8cCg1fJGDF", blog_url="https://www.geeksforgeeks.org/introduction-to-simulation-modeling/", body="Discrete-event simulation, random number generation, queuing theory, GPSS fundamentals, output analysis, and model validation."),
            Resource(course_id=courses_by_code["COSC416"].id, created_by_id=researcher.id, title="Queuing Theory - Practical Applications", resource_type="blog", difficulty="advanced", estimated_minutes=15, blog_url="https://www.geeksforgeeks.org/queuing-theory/", video_url="https://www.youtube.com/watch?v=IPLx4LfQo5k", body="Understanding M/M/1 queues, Little's Law, utilization analysis, and how queuing theory applies to computer systems and networks."),
            Resource(course_id=courses_by_code["SECS403"].id, created_by_id=researcher.id, title="Research Methods for CS Education", resource_type="video", difficulty="intermediate", estimated_minutes=60, video_url="https://www.youtube.com/watch?v=PDjS20kic54", blog_url="https://www.geeksforgeeks.org/research-methodology/", body="CS education research design: problem statement, literature review, theoretical frameworks, quasi-experimental design, and data analysis."),
            Resource(course_id=courses_by_code["SECS403"].id, created_by_id=researcher.id, title="Academic Writing & Thesis Structure", resource_type="blog", difficulty="intermediate", estimated_minutes=20, blog_url="https://www.geeksforgeeks.org/how-to-write-a-research-paper/", video_url="https://www.youtube.com/watch?v=KNT6k-DRS8M", body="How to structure a research thesis: abstract, introduction, methodology, results, discussion, and references with formatting tips."),
        ]
        db.add_all(resources)
        db.flush()

    seed_quiz_banks(db, courses_by_code)
    seed_practical_exercises(db, courses_by_code)
    seed_surveys(db)
    db.commit()


def seed_surveys(db: Session) -> None:
    if db.scalar(select(func.count(Survey.id))) > 0:
        return

    pre = Survey(
        title="Pre-Intervention Survey",
        survey_type="presurvey",
        description="Baseline assessment of your attitudes toward computer science, learning self-efficacy, and technology acceptance.",
    )
    post = Survey(
        title="Post-Intervention Survey",
        survey_type="postsurvey",
        description="Follow-up assessment of how your attitudes, self-efficacy, and technology acceptance may have changed.",
    )
    db.add_all([pre, post])
    db.flush()

    pre_questions = [
        ("I am confident I can learn computer science concepts.", "self_efficacy", 0),
        ("I can solve challenging programming problems on my own.", "self_efficacy", 1),
        ("I am confident explaining CS concepts to a classmate.", "self_efficacy", 2),
        ("I enjoy learning about computer science.", "attitude", 3),
        ("Computer science is relevant to my career goals.", "attitude", 4),
        ("I find programming intellectually stimulating.", "attitude", 5),
        ("CS education research can improve how we teach computing.", "attitude", 6),
        ("I believe I can succeed in a computing-related career.", "self_efficacy", 7),
        ("I prefer figuring out programming problems rather than being told the answer.", "attitude", 8),
        ("Technology can make learning more engaging.", "tech_acceptance", 9),
        ("I am comfortable using online platforms for learning.", "tech_acceptance", 10),
        ("I would recommend a learning platform like this to peers.", "tech_acceptance", 11),
    ]

    post_questions = [
        ("My confidence in learning CS concepts has improved.", "self_efficacy", 0),
        ("I can now solve more challenging programming problems.", "self_efficacy", 1),
        ("I feel more confident explaining CS concepts to others.", "self_efficacy", 2),
        ("My interest in computer science has grown.", "attitude", 3),
        ("I see more clearly how CS relates to my career.", "attitude", 4),
        ("Programming challenges are more engaging than before.", "attitude", 5),
        ("Participating in this research helped me appreciate CS education.", "attitude", 6),
        ("I believe more strongly I can succeed in computing.", "self_efficacy", 7),
        ("I am now more proactive in solving programming problems.", "attitude", 8),
        ("Using this platform improved my learning experience.", "tech_acceptance", 9),
        ("I found the online platform easy to use.", "tech_acceptance", 10),
        ("I would like to continue using platforms like this for learning.", "tech_acceptance", 11),
    ]

    for prompt, dimension, order_idx in pre_questions:
        db.add(SurveyQuestion(survey_id=pre.id, prompt=prompt, dimension=dimension, order_index=order_idx))

    for prompt, dimension, order_idx in post_questions:
        db.add(SurveyQuestion(survey_id=post.id, prompt=prompt, dimension=dimension, order_index=order_idx))

    db.flush()


def reset_stale_sqlite_schema() -> None:
    from sqlalchemy import inspect as sa_inspect

    if not engine.url.drivername.startswith("sqlite"):
        return

    with engine.connect() as connection:
        inspector = sa_inspect(connection)
        table_names = inspector.get_table_names()
        if "courses" in table_names:
            return

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table_name in table_names:
            safe_name = table_name.replace('"', '""')
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{safe_name}"')
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
