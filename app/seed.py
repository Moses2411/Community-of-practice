from datetime import datetime
from pathlib import Path

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.config import QUIZ_ROUND_SIZE
from app.course_banks import COURSE_QUESTION_BANK
from app.utils import generate_research_id, hash_password, log_activity, normalized_email
from db.database import Base, engine, SessionLocal
from model import (
    ConsentRecord,
    Course,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    Resource,
    User,
)


def ensure_seed_quiz(db: Session, course: Course, quiz_type: str, title: str, description: str) -> Quiz:
    existing = db.scalar(select(Quiz).where(Quiz.course_id == course.id, Quiz.quiz_type == quiz_type))
    if existing:
        return existing
    quiz = Quiz(course_id=course.id, title=title, quiz_type=quiz_type, description=description)
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

        pretest = ensure_seed_quiz(
            db,
            course,
            "pretest",
            f"{course.title} Pre-test",
            "Seven-question baseline assessment for this course before the learning intervention.",
        )
        practice = ensure_seed_quiz(
            db,
            course,
            "practice",
            f"{course.title} Practice Rounds",
            "Randomized seven-question practice rounds drawn from a larger university-level question bank.",
        )
        posttest = ensure_seed_quiz(
            db,
            course,
            "posttest",
            f"{course.title} Post-test",
            "Seven-question outcome assessment for this course after the learning intervention.",
        )

        ensure_seed_questions(db, pretest, bank)
        ensure_seed_questions(db, practice, bank)
        ensure_seed_questions(db, posttest, bank)


def seed_database(db: Session) -> None:
    researcher_email = normalized_email(
        "researcher@abuzaria.edu.ng"
    )
    researcher_password = "Research@12345"

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
            department="Computer Science",
            level="Research",
            interests="Community of practice analytics",
        )
        db.add(researcher)
        db.flush()

    if db.scalar(select(func.count(Course.id))) == 0:
        courses = [
            Course(
                title="Introduction To Computing",
                code="COSC101",
                description="Computer systems, hardware components, operating systems, office applications, and internet tools.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Object-Oriented Programming I",
                code="COSC211",
                description="Introduction to object-orientation, data types, control structures, arrays, recursion, and inheritance.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Data Structures and Algorithm",
                code="COSC301",
                description="Big-O analysis, stacks, queues, lists, trees, graphs, hash tables, and algorithm design strategies.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Database Management Systems",
                code="COSC309",
                description="Conceptual modeling, relational theory, SQL, normalization, security, query processing, and transactions.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Web Applications Engineering I",
                code="COSC307",
                description="Web architecture, XHTML, CSS, JavaScript, DOM, client-server interaction, and multimedia integration.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Operating Systems",
                code="COSC411",
                description="Process management, CPU scheduling, memory and virtual memory, file systems, I/O, and security.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Discrete Structures",
                code="COSC203",
                description="Functions, relations, counting, graphs, trees, discrete probability, and recurrence relations.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Organization and Assembly Language",
                code="COSC204",
                description="Computer organization, number representation, assembly programming, addressing modes, and interrupts.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Digital Logic Design",
                code="COSC205",
                description="Boolean algebra, combinational and sequential circuits, flip-flops, multiplexers, and memory elements.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Human Computer Interaction",
                code="COSC206",
                description="HCI foundations, GUI principles, usability evaluation, user-centered design, and interaction design.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Introduction to Artificial Intelligence",
                code="COSC208",
                description="Problem-solving, knowledge representation, expert systems, natural language processing, and machine learning.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Object-Oriented Programming II",
                code="COSC212",
                description="Advanced OOP, polymorphism, interfaces, packages, API usage, recursion, and event-driven programming.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Computer Architecture",
                code="COSC303",
                description="Memory hierarchy, cache, pipelining, superscalar architecture, RISC, and parallel architectures.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Systems Analysis and Design",
                code="COSC305",
                description="SDLC, UML modelling, use cases, sequence diagrams, class diagrams, CASE tools, and project management.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Organization of Programming Languages",
                code="COSC311",
                description="Syntax and semantics, data types, control structures, subprograms, exception handling, and programming paradigms.",
                facilitator="Computer Science Education Facilitator",
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
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Formal Methods in Software Development",
                code="COSC402",
                description="Z notation, Hoare logic, BNF, model checking, finite state machines, temporal logic, and verification.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Software Engineering",
                code="COSC403",
                description="Design patterns, coupling, cohesion, MVC, refactoring, UML, information hiding, and software process models.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Network Design and Management",
                code="COSC404",
                description="Network design methodologies, SNMP, RMON, MIB, fault management, configuration management, and NOC operations.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Web Applications Engineering II",
                code="COSC405",
                description="Server-side development, session management, input validation, cookies, database integration, and web security.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Advanced Database Systems",
                code="COSC406",
                description="Concurrency control, distributed databases, CAP theorem, object-oriented databases, query optimisation, and recovery.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Data Communications and Networks",
                code="COSC407",
                description="OSI model, TCP/IP, routing, DNS, Ethernet, subnetting, network topologies, and data link protocols.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Compiler Construction",
                code="COSC408",
                description="Lexical analysis, parsing, semantic analysis, symbol tables, intermediate code, optimisation, and code generation.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Professional and Social Aspects of Computing",
                code="COSC409",
                description="Professional ethics, intellectual property, data protection, computer crime, privacy, and social impact of IT.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Computational Science and Numerical Methods",
                code="COSC413",
                description="High-performance computing, parallel programming, scientific visualization, GPU computing, and numerical methods.",
                facilitator="Computer Science Education Facilitator",
            ),
            Course(
                title="Simulation Methodology",
                code="COSC416",
                description="Discrete-event simulation, random number generation, queuing theory, GPSS, output analysis, and model validation.",
                facilitator="Computer Science Education Facilitator",
            ),
        ]
        db.add_all(courses)
        db.flush()

    courses_by_code = {course.code: course for course in db.scalars(select(Course)).all()}

    if db.scalar(select(func.count(Resource.id))) == 0:
        resources = [
            Resource(
                course_id=courses_by_code["COSC101"].id,
                created_by_id=researcher.id,
                title="Computer Hardware Basics",
                resource_type="note",
                difficulty="beginner",
                estimated_minutes=10,
                body=(
                    "A computer system consists of input devices, output devices, the system unit, "
                    "and storage. The CPU executes instructions, RAM provides temporary storage, "
                    "and the hard drive or SSD stores data permanently."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC211"].id,
                created_by_id=researcher.id,
                title="Getting Started with Java Programming",
                resource_type="guide",
                difficulty="beginner",
                estimated_minutes=10,
                body=(
                    "Before asking for help, check the error message, identify the line number, "
                    "read variable values, test one small change, and explain what you expected."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC301"].id,
                created_by_id=researcher.id,
                title="Choosing the Right Data Structure",
                resource_type="note",
                difficulty="intermediate",
                estimated_minutes=18,
                body=(
                    "Use arrays for indexed access, stacks for last-in-first-out workflows, queues "
                    "for first-in-first-out tasks, hash tables for fast lookup, and trees for hierarchy."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC309"].id,
                created_by_id=researcher.id,
                title="Normalization in Plain Language",
                resource_type="note",
                difficulty="intermediate",
                estimated_minutes=20,
                body=(
                    "Normalization reduces repeated data and update errors. First normal form removes "
                    "repeating groups, second normal form removes partial dependency, and third normal "
                    "form removes transitive dependency."
                ),
            ),
            Resource(
                course_id=courses_by_code["SECS403"].id,
                created_by_id=researcher.id,
                title="Conducting Research in CS Education",
                resource_type="research-support",
                difficulty="beginner",
                estimated_minutes=8,
                body=(
                    "A CS education research project typically includes a statement of the problem, "
                    "literature review, theoretical framework, research questions, methodology, "
                    "data analysis, findings, discussion, and conclusions. Ethical approval and "
                    "informed consent are required before data collection begins."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC203"].id,
                created_by_id=researcher.id,
                title="Discrete Structures Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.mheducation.com/highered/product/discrete-mathematics-applications-rosen/M9780073383095.html",
                video_url="https://youtube.com/playlist?list=PLl-gb0E4MII28GykmtuBXNUNoejvY5Rir",
                blog_url="https://medium.com/@csmath/discrete-mathematics-for-cs",
                body=(
                    "1. K. Rosen, Discrete Mathematics and Its Applications, 6th Ed., McGraw-Hill, 2007. "
                    "2. F. Giannasi and R. Low, Maths for Computing and IT, Longman, 1996. "
                    "3. J. Truss, Discrete Mathematics for Computer Scientists, Addison-Wesley, 1999."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC204"].id,
                created_by_id=researcher.id,
                title="Assembly Language Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/computer-system-design-architecture",
                video_url="https://youtube.com/playlist?list=PLxN4E629oPnJ2ayhPfmwQBb2M4QGRXxLd",
                blog_url="https://www.reversinglabs.com/blog/assembly-language-basics",
                body=(
                    "1. Vincent P. Heuring, Harry F. Jordan, Computer System Design & Architecture, Prentice Hall, 2004. "
                    "2. Dandamudi et al, Introduction to Assembly Language Programming: From 8086 to Pentium, Springer, 1998."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC205"].id,
                created_by_id=researcher.id,
                title="Digital Logic Design Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/logic-computer-design-fundamentals",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjMH3mWf6klqiB7d0cO1sOX",
                blog_url="https://www.allaboutcircuits.com/technical-articles/digital-logic-design/",
                body=(
                    "1. M. M. Mano and C. R. Kime, Logic and Computer Design Fundamentals & XILINX 6.3, 3rd Ed., Prentice Hall, 2004. "
                    "2. Englander, The Architecture of Computer Hardware and Systems Software, 3rd Ed., Wiley, 2003."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC206"].id,
                created_by_id=researcher.id,
                title="HCI Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/human-computer-interaction",
                video_url="https://youtube.com/playlist?list=PLVHgdkG5gPpgrJ7IUjjYKq8cf6PNKFWaR",
                blog_url="https://www.interaction-design.org/literature/topics/human-computer-interaction",
                body=(
                    "1. Dix, Finlay, Aboud & Beale, Human-Computer Interaction, 3rd Ed., Pearson, 2004. "
                    "2. Preece, J., Rogers, Y. & Sharp, H., Interaction Design: Beyond Human-Computer Interaction, Wiley, 2002."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC208"].id,
                created_by_id=researcher.id,
                title="Artificial Intelligence Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/artificial-intelligence-modern-approach",
                video_url="https://youtube.com/playlist?list=PLUl4u3cNGP63gFHB6xb-kVBiQHYe_4hSi",
                blog_url="https://machinelearningmastery.com/blog/",
                body=(
                    "1. Stuart Russell and Peter Norvig, AI: A Modern Approach, 2nd Ed., Prentice Hall, 2003. "
                    "2. G.F. Luger, Artificial Intelligence: Structures and Strategies, 5th Ed., Addison Wesley, 2005."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC212"].id,
                created_by_id=researcher.id,
                title="OOP II Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.jblearning.com/catalog/productdetails/9780763757959",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjWmhQlw8UvyQ7nYb3Q0g5R",
                blog_url="https://www.geeksforgeeks.org/object-oriented-programming-in-java/",
                body=(
                    "1. Nell Dale and Chip Weems, Programming and Problem Solving with Java, 2nd Ed., Jones and Bartlett, 2008. "
                    "2. J. Lewis and W. Loftus, Java Software Solutions, 5th Ed., Addison Wesley, 2006. "
                    "3. D.J. Barnes and M.K. Kolling, Objects First with Java, Pearson, 2006."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC303"].id,
                created_by_id=researcher.id,
                title="Computer Architecture Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.elsevier.com/books/computer-architecture/patterson/978-0-12-370490-0",
                video_url="https://youtube.com/playlist?list=PL5PHm2jkkXmi5CxxI7b3JCL1HvKZ5J0Wq",
                blog_url="https://www.computerscience.gcse.guru/theory/computer-architecture",
                body=(
                    "1. David Patterson & John Hennessy, Computer Architecture: A Quantitative Approach, 4th Ed., Kaufmann, 2006. "
                    "2. Linda Null and Julia Lobur, The Essentials of Computer Organization and Architecture, 2nd Ed., Jones & Bartlett, 2006."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC305"].id,
                created_by_id=researcher.id,
                title="Systems Analysis and Design Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.wiley.com/en-us/Systems+Analysis+and+Design%2C+3rd+Edition-p-9780471756125",
                video_url="https://youtube.com/playlist?list=PLWPirh4EWFpFU1__BKbXHqV3N_7GJxN0t",
                blog_url="https://www.visual-paradigm.com/guide/uml/",
                body=(
                    "1. Dennis, Wixom, Roth, Systems Analysis and Design, 3rd Ed., John Wiley, 2006. "
                    "2. Bennett, McRobb & Farmer, Object Oriented Systems Analysis and Design Using UML, 3rd Ed., McGraw-Hill, 2006. "
                    "3. Roger S. Pressman, Software Engineering: A Practitioner's Approach, 6th Ed., McGraw-Hill, 2005."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC311"].id,
                created_by_id=researcher.id,
                title="Programming Languages Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/concepts-of-programming-languages",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW0T4_7kPZOBWw4aE6QaX9",
                blog_url="https://dev.to/t/programminglanguages",
                body=(
                    "1. Robert W. Sebesta, Concepts of Programming Languages, 7th Ed., Addison-Wesley, 2006. "
                    "2. Kenneth Louden, Programming Languages: Principles and Practice, 2nd Ed., Course Technology, 2003. "
                    "3. Allen Tucker and Robert Noonan, Programming Languages: Principles and Paradigms, McGraw-Hill, 2002."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC401"].id,
                created_by_id=researcher.id,
                title="Algorithms Textbooks",
                resource_type="reference",
                difficulty="advanced",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/introduction-to-the-design-analysis-of-algorithms",
                video_url="https://youtube.com/playlist?list=PLUl4u3cNGP63EdVPNLG3ToM6LaEUuStmh",
                blog_url="https://www.geeksforgeeks.org/fundamentals-of-algorithms/",
                body=(
                    "1. Anany Levitin, Introduction to the Design and Analysis of Algorithms, Addison Wesley, 2003. "
                    "2. M. Al-Suwaiyel, Algorithms: Design Techniques & Analysis, World Scientific, 1999. "
                    "Online: http://www.cs.ucsd.edu/classes/wi05/cse101/"
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC402"].id,
                created_by_id=researcher.id,
                title="Formal Methods Textbooks",
                resource_type="reference",
                difficulty="advanced",
                estimated_minutes=5,
                url="https://www.cambridge.org/core/books/logic-in-computer-science/E3A1E2F1A1C2B3D4E5F6A7B8C9D0E1F2",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://medium.com/@formalmethods/introduction-to-formal-methods",
                body=(
                    "1. Jonathan Bowen, Formal Specification and Documentation using Z, ITCP, 1996. "
                    "2. Huth, M. and Ryan, M., Logic in Computer Science, Cambridge University Press, 1999. "
                    "3. Cliff B. Jones, Systematic Software Development Using VDM, 2nd Ed., Prentice Hall, 1990."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC403"].id,
                created_by_id=researcher.id,
                title="Software Engineering Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.mheducation.com/highered/product/software-engineering-practitioner-s-approach-pressman/M9780078022128.html",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW0T4_7kPZOBWw4aE6QaX9",
                blog_url="https://martinfowler.com/bliki/",
                body=(
                    "1. Roger S. Pressman, Software Engineering: A Practitioner's Approach, 6th Ed., McGraw-Hill, 2005. "
                    "2. Ian Sommerville, Software Engineering, 8th Ed., Addison Wesley, 2006. "
                    "3. Dennis, Wixom, Roth, Systems Analysis and Design, 3rd Ed., John Wiley, 2006."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC404"].id,
                created_by_id=researcher.id,
                title="Network Design Textbooks",
                resource_type="reference",
                difficulty="advanced",
                estimated_minutes=5,
                url="https://www.elsevier.com/books/network-analysis-architecture-and-design/mccabe/978-0-12-370490-0",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://www.networkcomputing.com/",
                body=(
                    "1. James D. McCabe, Network Analysis, Architecture and Design, 2nd Ed., Morgan Kaufmann, 2003. "
                    "2. Rachel Morgan and Henry McGilton, Introducing Unix System V, McGraw-Hill, 1987."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC405"].id,
                created_by_id=researcher.id,
                title="Web Applications II Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/internet-world-wide-web-how-to-program",
                video_url="https://youtube.com/playlist?list=PLbWDhxwM_45mPVToY0s4g3GjFZ7s0b5f5",
                blog_url="https://developer.mozilla.org/en-US/",
                body=(
                    "1. Dietel, Dietel, Goldberg, Internet & World Wide Web How to Program, 4th Ed., Prentice-Hall, 2007. "
                    "2. Jeffrey C. Jackson, Web Technologies: A Computer Science Perspective, Prentice Hall, 2007. "
                    "3. Shepherd, G., Microsoft ASP.NET 2.0 Step by Step, Microsoft, 2006."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC406"].id,
                created_by_id=researcher.id,
                title="Advanced Database Textbooks",
                resource_type="reference",
                difficulty="advanced",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/fundamentals-of-database-systems",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://db-engines.com/en/blog",
                body=(
                    "1. Ramez Elmasri and Shamkant B. Navathe, Fundamentals of Database Systems, 5th Ed., Addison-Wesley, 2007. "
                    "2. Carolyn Begg and Thomas Connolly, Database Systems: A Practical Approach, 4th Ed., Prentice Hall, 2004."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC407"].id,
                created_by_id=researcher.id,
                title="Data Communications Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.mheducation.com/highered/product/data-communications-networking-forouzan/M9780072967753.html",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://www.networkworld.com/",
                body=(
                    "1. Behrouz A. Forouzan, Data Communications and Networking, McGraw-Hill, 2004. "
                    "2. Andrew Tanenbaum, Computer Networks, 4th Ed., Prentice Hall, 2003."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC408"].id,
                created_by_id=researcher.id,
                title="Compiler Construction Textbooks",
                resource_type="reference",
                difficulty="advanced",
                estimated_minutes=5,
                url="https://www.cambridge.org/core/books/modern-compiler-implementation-in-java/3E1A2F1A1C2B3D4E5F6A7B8C9D0E1F2",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://craftinginterpreters.com/",
                body=(
                    "1. Andrew W. Appel, Modern Compiler Implementation in Java, 2nd Ed., Cambridge University Press, 2002. "
                    "2. ACM/IEEE Computing Curricula 2001: http://www.acm.org/sigcse/cc2001 "
                    "3. NUC BMAS Benchmarks, National Universities Commission, 2007."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC409"].id,
                created_by_id=researcher.id,
                title="Professional and Social Aspects Textbooks",
                resource_type="reference",
                difficulty="intermediate",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/ethics-in-information-technology",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://www.eff.org/blog",
                body=(
                    "1. David Bainbridge, Introduction to Information Technology Law, 6th Ed., Longman, 2007. "
                    "2. George Reynolds, Ethics in Information Technology, Course Technology, 2006."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC413"].id,
                created_by_id=researcher.id,
                title="Computational Science Textbooks",
                resource_type="reference",
                difficulty="advanced",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/parallel-programming-techniques-applications",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://www.hpcwire.com/",
                body=(
                    "1. Barry Wilkinson and Michael Allen, Parallel Programming: Techniques and Applications, 2nd Ed., Prentice-Hall, 2005. "
                    "2. Michael J. Quinn, Parallel Programming in C with MPI and OpenMP, McGraw-Hill, 2003."
                ),
            ),
            Resource(
                course_id=courses_by_code["COSC416"].id,
                created_by_id=researcher.id,
                title="Simulation Methodology Textbooks",
                resource_type="reference",
                difficulty="advanced",
                estimated_minutes=5,
                url="https://www.pearson.com/en-us/subject-catalog/p/system-simulation",
                video_url="https://youtube.com/playlist?list=PLBlnK6fEyqRjW7h6r5S5g5f5b5f5b5f5b5",
                blog_url="https://www.informs.org/Blog",
                body=(
                    "1. Gordon G., System Simulation, Prentice Hall. "
                    "2. Payer T.A., Introduction to Simulation, McGraw-Hill."
                ),
            ),
        ]
        db.add_all(resources)
        db.flush()

    seed_quiz_banks(db, courses_by_code)
    db.commit()


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
