from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import random
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Iterable

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import Base, SessionLocal, engine, get_db
from model import (
    AcademicRecord,
    ActivityLog,
    ConsentRecord,
    Course,
    DiscussionReply,
    DiscussionThread,
    Membership,
    PlatformFeedback,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    ReplyHelpfulVote,
    Resource,
    ResourceFeedback,
    ResourceView,
    Reflection,
    User,
)
from schemas import (
    AcademicRecordCreate,
    ActivityCreate,
    ConsentCreate,
    CourseCreate,
    DiscussionReplyCreate,
    DiscussionThreadCreate,
    MembershipCreate,
    PlatformFeedbackCreate,
    QuizCreate,
    QuizQuestionCreate,
    QuizSubmit,
    ReflectionCreate,
    ResourceCreate,
    ResourceFeedbackCreate,
    UserCreate,
    UserLogin,
)


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

RESEARCH_ROLES = {"researcher", "admin"}
CONTENT_ROLES = {"facilitator", "researcher", "admin"}
QUIZ_ROUND_SIZE = 7


def bank_question(
    prompt: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_option: str,
    explanation: str,
) -> dict:
    return {
        "prompt": prompt,
        "option_a": option_a,
        "option_b": option_b,
        "option_c": option_c,
        "option_d": option_d,
        "correct_option": correct_option,
        "explanation": explanation,
        "points": 1,
    }


COURSE_QUESTION_BANK = {
    "COSC101": [
        bank_question(
            "What is the primary function of the Central Processing Unit (CPU) in a computer system?",
            "Store data permanently on the hard drive",
            "Execute instructions and process data",
            "Display graphics on the monitor",
            "Connect to the internet wirelessly",
            "b",
            "The CPU executes program instructions and performs arithmetic and logic operations on data.",
        ),
        bank_question(
            "Which of the following is an example of system software?",
            "Microsoft Word",
            "Windows Operating System",
            "Adobe Photoshop",
            "Google Chrome",
            "b",
            "System software manages hardware and provides a platform for application software; the OS is the primary example.",
        ),
        bank_question(
            "What type of application is Microsoft Excel primarily used for?",
            "Text formatting and document creation",
            "Numerical data organisation and calculations",
            "Email communication and scheduling",
            "Image editing and graphic design",
            "b",
            "Excel is a spreadsheet application designed for numerical data, formulas, charts, and analysis.",
        ),
        bank_question(
            "Which hardware component temporarily holds data and instructions for currently running programs?",
            "Hard Disk Drive",
            "Random Access Memory (RAM)",
            "Central Processing Unit",
            "Power Supply Unit",
            "b",
            "RAM is volatile memory that stores active data and code for quick CPU access.",
        ),
        bank_question(
            "What tool is used to locate, retrieve, and display content on the World Wide Web?",
            "Email client",
            "Web browser",
            "File transfer utility",
            "Database management system",
            "b",
            "A web browser sends HTTP requests and renders HTML pages from web servers.",
        ),
        bank_question(
            "What does URL stand for?",
            "Universal Reference Link",
            "Uniform Resource Locator",
            "Unified Resource Listing",
            "Universal Retrieval Locator",
            "b",
            "A URL specifies the location of a resource on the Internet and the protocol used to access it.",
        ),
        bank_question(
            "Which storage technology typically provides the fastest read and write speeds?",
            "Hard Disk Drive (HDD)",
            "Solid State Drive (SSD)",
            "Compact Disc (CD-ROM)",
            "Floppy Disk",
            "b",
            "SSDs use flash memory with no moving parts, giving much faster access than spinning HDDs.",
        ),
        bank_question(
            "Which of the following is an input device?",
            "Monitor",
            "Speaker",
            "Keyboard",
            "Printer",
            "c",
            "A keyboard sends data to the computer; monitors, speakers, and printers are output devices.",
        ),
        bank_question(
            "What is the main purpose of an operating system?",
            "Create and edit documents",
            "Manage computer hardware and software resources",
            "Browse the internet efficiently",
            "Design professional graphics",
            "b",
            "The OS manages processes, memory, devices, files, and provides a user interface.",
        ),
        bank_question(
            "Which generation of computers introduced integrated circuits?",
            "First generation",
            "Second generation",
            "Third generation",
            "Fourth generation",
            "c",
            "Third-generation computers (1960s-70s) used integrated circuits instead of discrete transistors.",
        ),
    ],
    "COSC211": [
        bank_question(
            "A student writes a loop that should terminate when a counter reaches 10, but it never stops. Which debugging step is most appropriate first?",
            "Rewrite the whole program in another language",
            "Trace the counter value and loop condition during execution",
            "Remove all functions from the program",
            "Increase the computer memory",
            "b",
            "Tracing the control variable and condition reveals whether the loop state is changing correctly.",
        ),
        bank_question(
            "In structured programming, why is a function usually preferred over repeated blocks of identical code?",
            "It always makes execution slower",
            "It improves reuse, readability, and testability",
            "It prevents the use of variables",
            "It removes the need for input validation",
            "b",
            "Functions reduce duplication and make a program easier to test and maintain.",
        ),
        bank_question(
            "Which statement best describes an algorithm before it is implemented in code?",
            "A hardware device that executes arithmetic",
            "A precise finite sequence of steps for solving a problem",
            "A database table that stores source files",
            "A visual theme for a user interface",
            "b",
            "An algorithm is a clear step-by-step procedure independent of a specific programming language.",
        ),
        bank_question(
            "Why is input validation important in introductory programming tasks?",
            "It ensures users can only provide data the program is prepared to process",
            "It guarantees every program has no syntax errors",
            "It replaces the need for testing",
            "It makes variables global by default",
            "a",
            "Validation prevents invalid data from producing incorrect or unsafe program behavior.",
        ),
        bank_question(
            "A local variable declared inside a function is usually inaccessible outside that function because of:",
            "Compilation speed",
            "Variable scope",
            "Screen resolution",
            "Network latency",
            "b",
            "Scope controls the region of a program where a name can be referenced.",
        ),
        bank_question(
            "Which testing approach checks small units of program logic such as individual functions?",
            "Load testing",
            "Unit testing",
            "Acceptance sampling",
            "Packet switching",
            "b",
            "Unit tests verify small, isolated pieces of logic.",
        ),
        bank_question(
            "What is the main risk of using a global variable for data that many functions modify?",
            "It cannot store numbers",
            "It can create hidden dependencies and make bugs harder to trace",
            "It prevents loops from executing",
            "It disables comments",
            "b",
            "Shared mutable global state can be changed from many places, making program behavior harder to reason about.",
        ),
        bank_question(
            "A recursive function must include a base case mainly to:",
            "Increase the number of imports",
            "Stop the recursion when a simple condition is reached",
            "Convert all strings to integers",
            "Prevent comments from compiling",
            "b",
            "The base case stops recursive calls and prevents infinite recursion.",
        ),
        bank_question(
            "Which condition is most likely to cause an off-by-one error?",
            "Using <= instead of < when processing indexed data",
            "Adding comments above every function",
            "Using a meaningful variable name",
            "Separating code into modules",
            "a",
            "Boundary comparisons often determine whether a loop runs one time too many or too few.",
        ),
        bank_question(
            "What does a compiler or interpreter usually report when source code violates language grammar?",
            "A syntax error",
            "A stakeholder analysis",
            "A network timeout",
            "A database deadlock",
            "a",
            "Syntax errors occur when code does not follow the language grammar.",
        ),
        bank_question(
            "Which programming practice best supports maintainability in a student project?",
            "Using unclear names to make code shorter",
            "Writing modular code with meaningful names and focused functions",
            "Putting all logic in one long function",
            "Avoiding tests until final submission",
            "b",
            "Modularity and naming help future readers understand and safely change code.",
        ),
        bank_question(
            "In problem solving, pseudocode is useful because it:",
            "Allows planning logic without being restricted by exact programming syntax",
            "Automatically runs on every operating system",
            "Encrypts source code",
            "Removes all errors from a final program",
            "a",
            "Pseudocode helps students reason about logic before implementation details.",
        ),
        bank_question(
            "Why should exception handling be used carefully rather than hiding all errors?",
            "Hidden errors can make failures harder to diagnose and correct",
            "Exceptions prevent variables from storing data",
            "All exceptions are caused by hardware faults",
            "Handling exceptions disables functions",
            "a",
            "Catching every error without reporting useful information can mask real defects.",
        ),
        bank_question(
            "A dry run of an algorithm means:",
            "Manually tracing the algorithm with sample input",
            "Deleting the source file before execution",
            "Installing a database server",
            "Compressing all program files",
            "a",
            "Dry running checks logic by hand before or alongside coding.",
        ),
        bank_question(
            "Which design choice most directly improves readability for peer review?",
            "Consistent indentation and descriptive identifiers",
            "Removing all whitespace",
            "Using only one-letter variable names",
            "Mixing unrelated tasks in one function",
            "a",
            "Readable formatting and identifiers help peers understand and comment on code.",
        ),
        bank_question(
            "What is the best interpretation of a Boolean expression in program control?",
            "A value or condition evaluated as true or false",
            "A storage format for large videos",
            "A type of external memory",
            "A way to disable function calls",
            "a",
            "Control structures such as if statements depend on true or false conditions.",
        ),
        bank_question(
            "Which activity best supports learning from programming mistakes?",
            "Recording the error, cause, fix, and lesson learned",
            "Deleting the code immediately",
            "Changing many unrelated lines at once",
            "Avoiding all peer feedback",
            "a",
            "Reflection on errors helps students transfer debugging knowledge to future tasks.",
        ),
        bank_question(
            "When a function has too many responsibilities, the best refactoring step is usually to:",
            "Break it into smaller functions with clear purposes",
            "Rename the file only",
            "Remove all comments",
            "Convert every value to a string",
            "a",
            "Focused functions are easier to test, reuse, and understand.",
        ),
        bank_question(
            "Which example best represents abstraction in introductory programming?",
            "Using a function called calculate_average without thinking about every internal step each time",
            "Writing the same formula in ten different places",
            "Saving code as an image",
            "Running code without input",
            "a",
            "Abstraction hides unnecessary detail behind a meaningful interface.",
        ),
        bank_question(
            "Why is it useful to test boundary values such as 0, 1, and the maximum allowed input?",
            "Many logic errors appear at the edges of valid input ranges",
            "Boundary tests only check spelling mistakes",
            "They replace the need for normal test cases",
            "They guarantee the operating system is updated",
            "a",
            "Boundary cases often expose incorrect comparisons and assumptions.",
        ),
        bank_question(
            "In a peer programming discussion, which question most directly improves problem diagnosis?",
            "What result did you expect, and what result did you actually get?",
            "Which laptop brand do you use?",
            "How many colors are in your editor theme?",
            "Can you make the code longer?",
            "a",
            "Contrasting expected and actual output focuses debugging on the failed behavior.",
        ),
    ],
    "COSC301": [
        bank_question(
            "Which data structure is most appropriate for implementing undo functionality in an editor?",
            "Queue",
            "Stack",
            "Hash table only",
            "Adjacency matrix",
            "b",
            "Undo removes the most recent action first, which is last-in-first-out behavior.",
        ),
        bank_question(
            "What is the average-case time complexity of searching for a key in a well-designed hash table?",
            "O(1)",
            "O(log n)",
            "O(n log n)",
            "O(n^2)",
            "a",
            "With a good hash function and controlled load factor, lookup is constant on average.",
        ),
        bank_question(
            "Binary search is more efficient than linear search mainly because it:",
            "Requires the input to be unsorted",
            "Repeatedly halves a sorted search space",
            "Checks every element twice",
            "Uses only linked lists",
            "b",
            "Binary search uses ordering to discard half of the remaining candidates each step.",
        ),
        bank_question(
            "Which traversal of a binary search tree visits keys in sorted order?",
            "Preorder",
            "Inorder",
            "Postorder",
            "Level-order only",
            "b",
            "Inorder traversal of a binary search tree processes left subtree, root, then right subtree.",
        ),
        bank_question(
            "Why can inserting at the head of a singly linked list be O(1)?",
            "Only the new node pointer and head pointer need updating",
            "All nodes must be shifted in memory",
            "The list must be sorted first",
            "A binary search is required",
            "a",
            "Head insertion does not require traversing or shifting existing nodes.",
        ),
        bank_question(
            "Which algorithmic technique is used by merge sort?",
            "Divide and conquer",
            "Backtracking only",
            "Greedy selection only",
            "Random hashing",
            "a",
            "Merge sort divides the array, sorts subarrays, and merges them.",
        ),
        bank_question(
            "A queue is the best model for:",
            "First-come-first-served process scheduling",
            "Recursive function calls",
            "Undo operations",
            "Depth-first traversal storage only",
            "a",
            "Queues remove items in the same order they arrive.",
        ),
        bank_question(
            "What is the main purpose of Big-O notation?",
            "To describe how resource use grows with input size",
            "To measure monitor brightness",
            "To encrypt an algorithm",
            "To count the number of programming languages used",
            "a",
            "Big-O abstracts growth rate as input size increases.",
        ),
        bank_question(
            "Which structure is typically used to implement a priority queue efficiently?",
            "Heap",
            "Plain stack",
            "Circular string",
            "Sequential text file only",
            "a",
            "Heaps support efficient insertion and removal of highest or lowest priority items.",
        ),
        bank_question(
            "In graph theory, breadth-first search is especially useful for finding:",
            "Shortest path length in an unweighted graph",
            "The fastest sorting algorithm for arrays",
            "The memory address of a variable",
            "The syntax errors in a source file",
            "a",
            "BFS explores by distance layers in unweighted graphs.",
        ),
        bank_question(
            "Which situation is most likely to cause a hash table collision?",
            "Two different keys map to the same array index",
            "A loop runs zero times",
            "A tree has no root",
            "A stack is empty",
            "a",
            "Collisions occur when distinct keys produce the same hash bucket.",
        ),
        bank_question(
            "Which sorting algorithm has O(n log n) average complexity and partitions around a pivot?",
            "Quick sort",
            "Bubble sort",
            "Selection sort",
            "Linear search",
            "a",
            "Quick sort partitions data around pivots and is O(n log n) on average.",
        ),
        bank_question(
            "A balanced binary search tree is useful because it:",
            "Keeps search, insertion, and deletion close to O(log n)",
            "Stores only characters",
            "Prevents all duplicate input automatically",
            "Eliminates the need for comparisons",
            "a",
            "Balancing prevents the tree from degenerating into a long chain.",
        ),
        bank_question(
            "Which representation is usually more space efficient for a sparse graph?",
            "Adjacency list",
            "Full adjacency matrix",
            "Four-dimensional array",
            "Sorted stack",
            "a",
            "Adjacency lists store only existing edges, which helps sparse graphs.",
        ),
        bank_question(
            "What does a stable sorting algorithm preserve?",
            "The relative order of records with equal keys",
            "The original memory address of every variable",
            "The exact indentation of source code",
            "The number of CPU cores",
            "a",
            "Stability matters when equal keys have secondary ordering information.",
        ),
        bank_question(
            "Which operation is expensive in a dynamic array when capacity is exceeded?",
            "Resizing and copying existing elements",
            "Reading the first element",
            "Checking the length variable only",
            "Comparing two integers",
            "a",
            "Growing a dynamic array can require allocating new storage and copying elements.",
        ),
        bank_question(
            "Depth-first search can be implemented naturally using:",
            "A stack or recursion",
            "A printer driver",
            "A sorted array only",
            "A database view",
            "a",
            "DFS follows a path deeply, which matches stack behavior.",
        ),
        bank_question(
            "Which recurrence commonly describes binary search?",
            "T(n) = T(n/2) + O(1)",
            "T(n) = T(n-1) + O(n)",
            "T(n) = 2T(n) + O(n)",
            "T(n) = O(n^3) only",
            "a",
            "Binary search solves one half-size subproblem plus constant work.",
        ),
        bank_question(
            "Why is a circular queue useful in array-based queue implementation?",
            "It reuses freed positions without shifting all elements",
            "It sorts items automatically",
            "It removes the need for capacity checks",
            "It converts arrays into trees",
            "a",
            "Circular indexing lets the queue wrap around available array space.",
        ),
        bank_question(
            "Which condition indicates stack underflow?",
            "Popping from an empty stack",
            "Pushing onto a nonempty stack",
            "Traversing a graph",
            "Sorting a full array",
            "a",
            "Underflow occurs when a removal operation is attempted on an empty structure.",
        ),
        bank_question(
            "In asymptotic analysis, constants are usually ignored because:",
            "Growth trend dominates for large input sizes",
            "Constants are illegal in algorithms",
            "Programs cannot multiply values",
            "Only syntax matters",
            "a",
            "Asymptotic notation focuses on dominant growth behavior.",
        ),
    ],
    "COSC309": [
        bank_question(
            "Which normal form primarily removes repeating groups from a relational table?",
            "First normal form",
            "Second normal form",
            "Third normal form",
            "Boyce-Codd normal form only",
            "a",
            "First normal form requires atomic values and removes repeating groups.",
        ),
        bank_question(
            "A foreign key is used mainly to:",
            "Enforce a relationship between rows in different tables",
            "Encrypt every field in a database",
            "Sort all query results automatically",
            "Replace all primary keys",
            "a",
            "Foreign keys preserve referential integrity across related tables.",
        ),
        bank_question(
            "Which SQL clause filters grouped aggregate results?",
            "HAVING",
            "WHERE only",
            "ORDER BY only",
            "INSERT",
            "a",
            "HAVING filters groups after aggregation.",
        ),
        bank_question(
            "What is a transaction?",
            "A logical unit of database work that should complete fully or not at all",
            "A table that stores only passwords",
            "A graphical database icon",
            "A network cable standard",
            "a",
            "Transactions group operations under ACID guarantees.",
        ),
        bank_question(
            "Which ACID property ensures committed data remains saved after a system failure?",
            "Durability",
            "Isolation",
            "Atomicity",
            "Consistency only",
            "a",
            "Durability means committed changes survive crashes.",
        ),
        bank_question(
            "An index can improve query performance because it:",
            "Allows faster lookup of rows matching indexed columns",
            "Deletes duplicate records automatically",
            "Removes the need for SQL",
            "Guarantees every query is correct",
            "a",
            "Indexes trade storage and write overhead for faster reads.",
        ),
        bank_question(
            "Which anomaly occurs when changing a fact requires updates in many rows?",
            "Update anomaly",
            "Packet anomaly",
            "Syntax anomaly",
            "Thread anomaly",
            "a",
            "Update anomalies result from redundant data storage.",
        ),
        bank_question(
            "In an ER model, a many-to-many relationship is usually implemented in a relational database using:",
            "A junction table",
            "A single Boolean field",
            "Only a primary key rename",
            "A file extension",
            "a",
            "A junction table stores references to both participating tables.",
        ),
        bank_question(
            "Which join returns rows that have matching values in both tables?",
            "INNER JOIN",
            "FULL OUTER JOIN only",
            "CROSS JOIN only",
            "DELETE JOIN",
            "a",
            "An inner join keeps only matching rows.",
        ),
        bank_question(
            "What is the main purpose of query normalization and schema design in learning systems?",
            "Reduce redundancy and preserve accurate learning records",
            "Make all records anonymous automatically",
            "Prevent users from logging in",
            "Replace application code",
            "a",
            "Good schema design supports data integrity and meaningful analysis.",
        ),
        bank_question(
            "Which isolation issue occurs when a transaction reads data written by another uncommitted transaction?",
            "Dirty read",
            "Hash collision",
            "Syntax error",
            "Stack overflow",
            "a",
            "Dirty reads expose uncommitted changes that may later be rolled back.",
        ),
        bank_question(
            "Which SQL statement is used to define a new table?",
            "CREATE TABLE",
            "SELECT ROW",
            "MAKE INDEX ONLY",
            "DISPLAY DATABASE",
            "a",
            "CREATE TABLE is a data definition language command.",
        ),
        bank_question(
            "Why should passwords not be stored as plain text in a user table?",
            "A database leak would expose usable credentials directly",
            "Plain text cannot be queried",
            "Plain text disables foreign keys",
            "SQL cannot store strings",
            "a",
            "Passwords should be hashed with a strong one-way algorithm and salt.",
        ),
        bank_question(
            "Which database object presents a saved query as a virtual table?",
            "View",
            "Trigger only",
            "Heap",
            "Socket",
            "a",
            "Views expose query results through a table-like interface.",
        ),
        bank_question(
            "What does a candidate key represent?",
            "A minimal set of attributes that can uniquely identify a row",
            "Any column with repeated values",
            "A field that must be a date",
            "A table with no constraints",
            "a",
            "Candidate keys are possible minimal unique identifiers.",
        ),
        bank_question(
            "Which operation combines rows from two union-compatible queries and removes duplicates?",
            "UNION",
            "JOIN ONLY",
            "GROUP BY",
            "ROLLBACK",
            "a",
            "UNION combines compatible result sets and removes duplicates by default.",
        ),
        bank_question(
            "A cascading delete should be used carefully because it:",
            "Can automatically remove related records",
            "Always improves query speed",
            "Encrypts child tables",
            "Prevents all mistakes",
            "a",
            "Cascade rules can delete dependent data when a parent row is removed.",
        ),
        bank_question(
            "Which design best stores quiz attempts and answers for research analysis?",
            "Separate attempts and answer rows linked by keys",
            "One text field containing all scores and comments",
            "A spreadsheet image",
            "A table with no user identifier",
            "a",
            "Separate normalized records support reliable analysis and export.",
        ),
        bank_question(
            "Which constraint prevents two users from registering with the same email address?",
            "UNIQUE",
            "CHECK only",
            "FOREIGN KEY only",
            "DEFAULT",
            "a",
            "A unique constraint prevents duplicate values in a column or set of columns.",
        ),
        bank_question(
            "What is the purpose of database backup in an educational research system?",
            "Protect research and learning data from accidental loss",
            "Increase typing speed",
            "Remove all need for consent",
            "Make queries invalid",
            "a",
            "Backups help preserve important records for learning and analysis.",
        ),
        bank_question(
            "Which concept best supports anonymized research export?",
            "Using research IDs instead of names in analysis files",
            "Publishing student passwords",
            "Removing all timestamps",
            "Combining all answers into one row",
            "a",
            "Research IDs help link records without exposing direct identity.",
        ),
    ],
    "COSC307": [
        bank_question(
            "In a RESTful API, which HTTP method is usually used to create a new resource?",
            "POST",
            "GET",
            "TRACE only",
            "HEAD only",
            "a",
            "POST is commonly used for creating server-side resources.",
        ),
        bank_question(
            "What does CORS control in a web application?",
            "Whether a browser allows cross-origin HTTP requests",
            "How a database normalizes tables",
            "How a CPU schedules processes",
            "Whether CSS can use colors",
            "a",
            "CORS is a browser security mechanism for cross-origin requests.",
        ),
        bank_question(
            "Why should API input be validated on the server even if the frontend also validates it?",
            "Clients can be bypassed or manipulated",
            "Frontend validation encrypts all data",
            "Server validation slows every query to zero",
            "Browsers cannot send invalid data",
            "a",
            "The server is the trust boundary and must reject invalid or unsafe input.",
        ),
        bank_question(
            "A JWT is commonly used to:",
            "Carry signed authentication claims between client and server",
            "Compile Python files",
            "Replace relational databases",
            "Style web pages",
            "a",
            "JSON Web Tokens can represent signed identity and role claims.",
        ),
        bank_question(
            "Which security risk is reduced by hashing passwords before storage?",
            "Credential exposure after a database leak",
            "Slow internet speed",
            "CSS layout shift",
            "Incorrect HTML headings",
            "a",
            "Password hashes reduce the harm of leaked user tables.",
        ),
        bank_question(
            "Which FastAPI feature is commonly used to inject a database session into route handlers?",
            "Dependencies",
            "CSS selectors",
            "DNS records",
            "Binary trees",
            "a",
            "FastAPI dependencies provide reusable request-time objects such as database sessions.",
        ),
        bank_question(
            "What does an ORM primarily help developers do?",
            "Map database tables to application objects",
            "Render images in a browser only",
            "Schedule CPU interrupts",
            "Encrypt network packets automatically",
            "a",
            "Object-relational mappers connect application models with relational tables.",
        ),
        bank_question(
            "Which status code most clearly indicates a successful resource creation?",
            "201 Created",
            "404 Not Found",
            "500 Internal Server Error",
            "401 Unauthorized",
            "a",
            "201 communicates that a new resource was created successfully.",
        ),
        bank_question(
            "Why is role-based access control important in a research learning platform?",
            "It restricts sensitive exports and admin actions to authorized users",
            "It removes all learning content",
            "It prevents students from reading resources",
            "It replaces user consent",
            "a",
            "Different roles should have different permissions over data and content.",
        ),
        bank_question(
            "Which design reduces the N+1 query problem?",
            "Loading related records intentionally rather than querying inside repeated loops",
            "Adding more repeated API endpoints",
            "Disabling indexes",
            "Using only plain text passwords",
            "a",
            "N+1 problems occur when each item causes an additional query.",
        ),
        bank_question(
            "What is the main purpose of CSRF protection?",
            "Prevent unwanted authenticated actions triggered from another site",
            "Compress JavaScript bundles",
            "Normalize database tables",
            "Schedule network packets",
            "a",
            "CSRF defenses protect state-changing requests from cross-site abuse.",
        ),
        bank_question(
            "In frontend design, why should important controls have clear labels or accessible names?",
            "To support usability and assistive technologies",
            "To hide them from keyboard users",
            "To make API responses larger",
            "To disable browser navigation",
            "a",
            "Accessible names help users and assistive technology understand controls.",
        ),
        bank_question(
            "Which deployment concern is most directly addressed by environment variables?",
            "Keeping configuration such as secrets separate from source code",
            "Making all routes public",
            "Preventing CSS from loading",
            "Removing database backups",
            "a",
            "Environment variables allow settings to change between environments without code edits.",
        ),
        bank_question(
            "What is API versioning useful for?",
            "Changing an API while reducing disruption to existing clients",
            "Preventing all user registration",
            "Replacing HTTP with SQL",
            "Removing authentication",
            "a",
            "Versioning helps manage compatibility as APIs evolve.",
        ),
        bank_question(
            "Which web feature is most appropriate for live discussion updates?",
            "WebSockets or server-sent events",
            "Static image tags only",
            "Database foreign keys only",
            "Password hashing only",
            "a",
            "Realtime channels push new messages without repeated manual refresh.",
        ),
        bank_question(
            "Why should an API return consistent error messages and status codes?",
            "Clients can handle failures predictably",
            "It guarantees users answer quizzes correctly",
            "It makes all data public",
            "It removes the need for logs",
            "a",
            "Consistent errors help frontend code and users recover from problems.",
        ),
        bank_question(
            "Which cache risk matters when displaying personalized quiz results?",
            "A shared cache might expose one student's results to another",
            "Caching makes databases impossible",
            "Caching removes HTML",
            "Caching prevents all authentication",
            "a",
            "Personal data should not be cached in a way that leaks across users.",
        ),
        bank_question(
            "What is the purpose of an activity log in this platform?",
            "Capture learning engagement events for later analysis",
            "Replace the database schema",
            "Hide all user actions from researchers",
            "Make quizzes unscorable",
            "a",
            "Activity logs turn meaningful learning actions into analyzable engagement data.",
        ),
        bank_question(
            "Which frontend behavior best supports a fair timed quiz?",
            "Record the served questions and elapsed time with the submission",
            "Let the browser choose correct answers",
            "Show all answers before submission",
            "Disable all validation",
            "a",
            "The server must know which round was shown and how long the attempt took.",
        ),
        bank_question(
            "Which principle is most relevant when designing API responses for dashboards?",
            "Return structured data that can be aggregated and visualized",
            "Return one long paragraph for every table",
            "Hide all numeric values",
            "Use random field names every request",
            "a",
            "Dashboards need consistent structured data for summaries and charts.",
        ),
        bank_question(
            "Why should file and database operations be separated from presentation code?",
            "Separation of concerns makes the app easier to test and maintain",
            "It prevents all network errors",
            "It removes the need for authentication",
            "It forces every page to be blank",
            "a",
            "Separating responsibilities keeps code easier to reason about.",
        ),
    ],
    "COSC411": [
        bank_question(
            "What is the main difference between a process and a thread?",
            "Threads within a process share resources, while processes have separate address spaces",
            "Processes cannot execute code",
            "Threads always require separate computers",
            "Processes are only used in databases",
            "a",
            "Threads are lighter execution units that share a process address space.",
        ),
        bank_question(
            "Which CPU scheduling algorithm can cause starvation if low-priority jobs wait indefinitely?",
            "Priority scheduling",
            "Round robin only",
            "First-come-first-served only",
            "Shortest path routing",
            "a",
            "Priority scheduling can starve lower-priority processes without aging.",
        ),
        bank_question(
            "Virtual memory allows a system to:",
            "Run programs using an address space larger than physical RAM",
            "Disable all storage devices",
            "Replace the CPU scheduler",
            "Prevent every page fault",
            "a",
            "Virtual memory maps logical addresses to physical memory and secondary storage.",
        ),
        bank_question(
            "A page fault occurs when:",
            "A referenced virtual memory page is not currently in physical memory",
            "A network packet is duplicated",
            "A database row is deleted",
            "A function returns a value",
            "a",
            "The operating system must load the missing page before execution continues.",
        ),
        bank_question(
            "Which condition is required for deadlock to occur?",
            "Circular wait",
            "Sorted arrays",
            "HTTP caching",
            "Foreign key deletion",
            "a",
            "Circular wait is one of the Coffman conditions for deadlock.",
        ),
        bank_question(
            "What is the purpose of mutual exclusion?",
            "Prevent simultaneous unsafe access to a shared resource",
            "Increase duplicate records",
            "Disable all threads",
            "Sort network packets",
            "a",
            "Mutual exclusion protects critical sections from race conditions.",
        ),
        bank_question(
            "A process that is waiting for an I/O operation to complete is in which state?",
            "Ready",
            "Running",
            "Waiting (blocked)",
            "Terminated",
            "c",
            "A process enters the waiting state when it cannot continue until some external event occurs.",
        ),
        bank_question(
            "A semaphore that only takes values 0 and 1 and is used to protect a critical section is called a:",
            "Counting semaphore",
            "Binary semaphore or mutex lock",
            "Spinlock",
            "Monitor",
            "b",
            "A binary semaphore ensures mutual exclusion by allowing only one thread into the critical section.",
        ),
        bank_question(
            "What is thrashing in an operating system?",
            "The CPU spends more time paging than executing user programs",
            "A process enters an infinite loop",
            "The system runs out of disk space",
            "The scheduler assigns too high a priority to a process",
            "a",
            "Thrashing occurs when excessive page faults cause the system to spend most of its time swapping.",
        ),
        bank_question(
            "Which page replacement algorithm replaces the page that will not be used for the longest period?",
            "First-In-First-Out (FIFO)",
            "Least Recently Used (LRU)",
            "Optimal (Belady's algorithm)",
            "Round Robin",
            "c",
            "The Optimal algorithm selects the page with the farthest future reference but is not implementable.",
        ),
        bank_question(
            "Belady's anomaly refers to the phenomenon where:",
            "Increasing the number of page frames can increase the page fault rate under FIFO",
            "Adding more RAM always reduces page faults",
            "A process terminates unexpectedly",
            "The CPU scheduler starves low-priority processes",
            "a",
            "Belady's anomaly is specific to FIFO page replacement under certain reference patterns.",
        ),
        bank_question(
            "Which disk scheduling algorithm services requests by moving the arm in one direction until no more requests exist?",
            "FCFS",
            "SCAN (elevator algorithm)",
            "Shortest Seek Time First",
            "Round Robin",
            "b",
            "The SCAN algorithm moves the disk arm continuously from one end of the disk to the other.",
        ),
        bank_question(
            "Which of the following is an example of interprocess communication (IPC)?",
            "A program calling a function within the same file",
            "Two processes exchanging data through a shared memory segment",
            "A web browser rendering a web page",
            "The CPU executing an arithmetic instruction",
            "b",
            "IPC mechanisms include shared memory, message passing, and pipes.",
        ),
        bank_question(
            "Which file-system concept maps file names to metadata and disk blocks?",
            "Inode or file control block",
            "HTTP header",
            "Foreign key",
            "CSS class",
            "a",
            "File systems use metadata structures to locate and manage file contents.",
        ),
        bank_question(
            "Which file allocation method uses an index block to point to data blocks, minimising external fragmentation?",
            "Contiguous allocation",
            "Linked allocation",
            "Indexed allocation",
            "Sequential allocation",
            "c",
            "Indexed allocation uses an index block containing pointers to the file's data blocks.",
        ),
        bank_question(
            "What is a context switch in an operating system?",
            "Switching the monitor from one display mode to another",
            "Saving the state of one process and restoring another",
            "Changing the IP address of a network interface",
            "Replacing a file in the file system",
            "b",
            "Context switching allows multiple processes to share a single CPU by saving and restoring state.",
        ),
        bank_question(
            "Which scheduling method gives each ready process a fixed time quantum?",
            "Round robin",
            "Priority without aging",
            "Shortest path first",
            "Depth-first search",
            "a",
            "Round robin cycles through processes using time slices.",
        ),
        bank_question(
            "Race conditions occur when:",
            "Program output depends on unpredictable timing of concurrent operations",
            "A database table is normalised",
            "An IP address is assigned",
            "A file is compressed",
            "a",
            "Race conditions arise from unsynchronised access to shared state.",
        ),
        bank_question(
            "Which of the following is a requirement for a correct solution to the critical section problem?",
            "Each process must have a unique priority number",
            "Progress: if no process is in its critical section, a waiting process must eventually enter",
            "The critical section must contain no more than three instructions",
            "All variables must be declared global",
            "b",
            "Progress ensures decisions about which process enters next cannot be postponed indefinitely.",
        ),
        bank_question(
            "Which deadlock handling strategy allows deadlock to occur and then breaks it?",
            "Deadlock prevention",
            "Deadlock avoidance",
            "Deadlock detection and recovery",
            "Deadlock ignorance",
            "c",
            "Detection and recovery allows deadlocks to form but provides mechanisms to detect and resolve them.",
        ),
        bank_question(
            "Which memory allocation issue happens when free memory exists but not in one large enough contiguous block?",
            "External fragmentation",
            "Internal fragmentation",
            "Packet collision",
            "Syntax exception",
            "a",
            "External fragmentation divides free memory into small unusable gaps between allocated blocks.",
        ),
    ],
    "SECS403": [
        bank_question(
            "According to Wenger's theory, a Community of Practice is defined by three key characteristics. Which are they?",
            "Domain, community, and practice",
            "Lectures, assignments, and exams",
            "Hardware, software, and networks",
            "Planning, execution, and evaluation",
            "a",
            "Wenger identifies domain (shared interest), community (mutual engagement), and practice (shared repertoire) as the three pillars.",
        ),
        bank_question(
            "Action research in computer science education typically follows which cyclical process?",
            "Plan, act, observe, reflect, then revise",
            "Hypothesise, test, conclude, publish",
            "Design, code, compile, deploy",
            "Lecture, assess, grade, repeat",
            "a",
            "Action research iterates through planning, action, observation, and reflection to improve practice.",
        ),
        bank_question(
            "Which research approach combines quantitative and qualitative methods to study CS education problems?",
            "Mixed-methods research",
            "Pure quantitative research only",
            "Pure qualitative research only",
            "Literature review only",
            "a",
            "Mixed-methods research integrates numerical data with rich qualitative insights for deeper understanding.",
        ),
        bank_question(
            "What is the primary purpose of a literature review in a CS education research project?",
            "Identify the gap, theoretical framework, and justify the study's relevance",
            "Summarise every paper ever written on computers",
            "List all programming languages in alphabetical order",
            "Describe the researcher's personal opinions about CS",
            "a",
            "A literature review situates the study within existing knowledge and establishes its contribution.",
        ),
        bank_question(
            "Which ethical principle requires that CS education research participants can withdraw at any time?",
            "Voluntary participation",
            "Maximum data collection",
            "Fastest possible completion",
            "Mandatory enrolment",
            "a",
            "Voluntary participation means participants are free to leave the study without penalty.",
        ),
        bank_question(
            "In CS education research, a quasi-experimental design is appropriate when:",
            "Random assignment to groups is not feasible in classroom settings",
            "All students must use the same software version",
            "The study involves only one participant",
            "No data needs to be collected",
            "a",
            "Classroom constraints often prevent full randomisation, making quasi-experimental designs practical.",
        ),
        bank_question(
            "Which qualitative method is most suitable for analysing open-ended reflections from CS students?",
            "Thematic analysis",
            "Binary classification",
            "Merge sort",
            "Linear regression",
            "a",
            "Thematic analysis identifies recurring patterns and themes in textual data such as student reflections.",
        ),
        bank_question(
            "What does Cronbach's alpha measure in CS education survey instruments?",
            "Internal consistency reliability of scale items",
            "The speed of program compilation",
            "Network bandwidth utilisation",
            "CPU clock frequency",
            "a",
            "Cronbach's alpha indicates whether multiple items consistently measure the same underlying construct.",
        ),
        bank_question(
            "Which sampling strategy is most commonly used when recruiting CS students from existing course sections?",
            "Convenience sampling",
            "Random sampling from the entire university",
            "Snowball sampling from alumni",
            "Stratified sampling by hair colour",
            "a",
            "Researchers typically use intact class sections, which is a form of convenience sampling.",
        ),
        bank_question(
            "A rubric for assessing programming assignments should include:",
            "Clear criteria for correctness, efficiency, readability, and testing",
            "Only the final output of the program",
            "The number of lines of code written",
            "The font style used in comments",
            "a",
            "Well-designed rubrics provide transparent, consistent criteria aligned with learning objectives.",
        ),
        bank_question(
            "What is the purpose of triangulation in CS education research?",
            "Strengthen credibility by corroborating evidence from multiple sources",
            "Eliminate all qualitative data from the study",
            "Ensure every student receives the same grade",
            "Reduce the word count of the final report",
            "a",
            "Triangulation uses different data types or collection methods to validate findings.",
        ),
        bank_question(
            "Which statistical test is appropriate for comparing the mean performance of experimental and control groups?",
            "Independent samples t-test",
            "Binary search",
            "Bubble sort",
            "DNS lookup",
            "a",
            "An independent-samples t-test determines whether group means differ significantly.",
        ),
        bank_question(
            "In a design-based research (DBR) approach, the researcher:",
            "Iteratively designs interventions and refines them based on classroom data",
            "Observes without any intervention",
            "Only conducts surveys at the end of the semester",
            "Avoids interaction with participants",
            "a",
            "DBR bridges theory and practice by testing and refining interventions in authentic settings.",
        ),
        bank_question(
            "Learning analytics in CS education typically uses log data to:",
            "Identify at-risk students and inform timely interventions",
            "Replace all human instructors with algorithms",
            "Grade programming assignments automatically without rubrics",
            "Track students' physical location on campus",
            "a",
            "Learning analytics applies educational data mining to improve student outcomes and support.",
        ),
        bank_question(
            "What should a statement of the problem in a CS education research project include?",
            "The gap in knowledge, its educational context, and why addressing it matters",
            "Only the budget for the research",
            "A list of all hardware used in the study",
            "The personal opinion of the researcher",
            "a",
            "A well-formed problem statement motivates the study by showing what is unknown and why it is important.",
        ),
        bank_question(
            "Which factor threatens the external validity of a CS education study conducted at a single institution?",
            "Limited generalizability to other institutions or populations",
            "The study cannot collect any quantitative data",
            "All participants already know the answers",
            "The researcher cannot write code",
            "a",
            "Single-institution studies may not represent broader populations, limiting generalisability.",
        ),
        bank_question(
            "What is the purpose of an operational definition in CS education research?",
            "Specify exactly how each variable will be measured",
            "Define the programming language syntax to be used",
            "Describe the colour scheme of the learning platform",
            "List the version numbers of all software installed",
            "a",
            "Operational definitions make abstract constructs measurable and replicable by other researchers.",
        ),
        bank_question(
            "Which data collection method is most appropriate for capturing students' collaborative problem-solving processes?",
            "Screen recording with think-aloud protocol",
            "Multiple-choice quiz only",
            "One-word survey response",
            "Counting how many times they press the keyboard",
            "a",
            "Think-aloud protocols and screen recordings reveal real-time reasoning and collaboration strategies.",
        ),
        bank_question(
            "A null hypothesis in CS education research typically states:",
            "There is no significant difference between the treatment and control conditions",
            "The intervention will definitely improve all student grades",
            "Every student will score 100 percent on the post-test",
            "The programming language used determines student intelligence",
            "a",
            "The null hypothesis asserts that observed effects are due to chance rather than the intervention.",
        ),
        bank_question(
            "Which conference outlet is specifically focused on computer science education research?",
            "SIGCSE Technical Symposium",
            "IEEE International Conference on Big Data",
            "ACM Conference on Computer Graphics",
            "International Conference on Machine Learning",
            "a",
            "SIGCSE is the ACM Special Interest Group on Computer Science Education conference.",
        ),
        bank_question(
            "What is the main advantage of using validated survey instruments in CS education research?",
            "They provide reliable and valid measures that can be compared across studies",
            "They automatically grade themselves",
            "They require no ethical approval",
            "They eliminate all need for statistical analysis",
            "a",
            "Validated instruments have established psychometric properties, enhancing research quality and comparability.",
        ),
    ],
    "COSC203": [
        bank_question(
            "Which principle guarantees that if n items are placed into m boxes and n > m, then at least one box contains more than one item?",
            "Pigeonhole principle",
            "Inclusion-exclusion principle",
            "Multiplication principle",
            "De Morgan's law",
            "a",
            "The pigeonhole principle is a fundamental counting argument used in discrete mathematics.",
        ),
        bank_question(
            "What is the cardinality of the power set of a set with 5 elements?",
            "10",
            "25",
            "32",
            "5",
            "c",
            "The power set has 2^n elements; 2^5 = 32.",
        ),
        bank_question(
            "Which of the following relations on a set is both symmetric and transitive but not necessarily reflexive?",
            "An equivalence relation",
            "A partial order",
            "A function",
            "A bijection",
            "a",
            "An equivalence relation is reflexive, symmetric, and transitive.",
        ),
        bank_question(
            "How many distinct permutations can be formed from the letters of the word 'MATH'?",
            "4",
            "12",
            "24",
            "16",
            "c",
            "4! = 4 x 3 x 2 x 1 = 24 distinct permutations.",
        ),
        bank_question(
            "A graph in which every pair of distinct vertices is connected by exactly one edge is called a:",
            "Tree",
            "Complete graph",
            "Bipartite graph",
            "Cycle graph",
            "b",
            "A complete graph Kn has n(n-1)/2 edges connecting all vertex pairs.",
        ),
        bank_question(
            "What is the solution to the recurrence relation T(n) = T(n-1) + n with T(0) = 0?",
            "T(n) = n",
            "T(n) = n(n+1)/2",
            "T(n) = 2^n",
            "T(n) = n^2",
            "b",
            "Expanding gives T(n) = 1 + 2 + ... + n = n(n+1)/2.",
        ),
        bank_question(
            "Which logical connective is true only when both operands are true?",
            "OR",
            "NOT",
            "AND",
            "XOR",
            "c",
            "The AND connective outputs true only when both inputs are true.",
        ),
        bank_question(
            "In a tree with n vertices, how many edges does it have?",
            "n - 1",
            "n",
            "n + 1",
            "2n",
            "a",
            "A tree with n vertices always has exactly n - 1 edges.",
        ),
        bank_question(
            "What is the probability of rolling a sum of 7 with two fair six-sided dice?",
            "1/6",
            "1/12",
            "1/36",
            "5/36",
            "a",
            "There are 6 combinations out of 36 that sum to 7: (1,6),(2,5),(3,4),(4,3),(5,2),(6,1).",
        ),
        bank_question(
            "Which of the following is NOT a valid propositional logical connective?",
            "AND",
            "OR",
            "PLUS",
            "IMPLIES",
            "c",
            "PLUS is an arithmetic operator, not a logical connective.",
        ),
    ],
    "COSC204": [
        bank_question(
            "In assembly language, which register typically holds the address of the next instruction to be executed?",
            "Accumulator",
            "Program counter",
            "Stack pointer",
            "Base register",
            "b",
            "The program counter (PC) or instruction pointer holds the address of the next instruction.",
        ),
        bank_question(
            "What is the two's complement representation of -6 in 8 bits?",
            "11111010",
            "00000110",
            "11111001",
            "10000110",
            "a",
            "Invert 00000110 to get 11111001, then add 1 to get 11111010.",
        ),
        bank_question(
            "Which addressing mode uses a register to hold the effective address of the operand?",
            "Immediate addressing",
            "Register indirect addressing",
            "Direct addressing",
            "Indexed addressing",
            "b",
            "In register indirect addressing, the register contains the memory address of the operand.",
        ),
        bank_question(
            "The MOV instruction in x86 assembly is used for:",
            "Arithmetic addition",
            "Data transfer between locations",
            "Conditional branching",
            "Loop control",
            "b",
            "MOV copies data from source to destination.",
        ),
        bank_question(
            "What does the stack pointer (SP) register track?",
            "The top of the stack",
            "The bottom of the stack",
            "The program counter value",
            "The status flags",
            "a",
            "SP always points to the top (most recently pushed item) of the call stack.",
        ),
        bank_question(
            "Which interrupt is commonly invoked to perform system calls in x86 architecture?",
            "INT 10h",
            "INT 21h",
            "INT 16h",
            "INT 13h",
            "b",
            "INT 21h is the DOS interrupt for system function calls.",
        ),
        bank_question(
            "ASCII code for uppercase 'A' is:",
            "65",
            "97",
            "48",
            "32",
            "a",
            "ASCII value of 'A' is 65 decimal (0x41).",
        ),
        bank_question(
            "The instruction 'JMP' in assembly language performs:",
            "Conditional jump",
            "Unconditional jump",
            "Jump if zero",
            "Call subroutine",
            "b",
            "JMP always transfers control to the target address unconditionally.",
        ),
        bank_question(
            "Which type of instruction allows arithmetic operations directly on memory operands?",
            "Register-to-register",
            "Memory-to-memory",
            "Register-to-memory",
            "Immediate",
            "c",
            "Register-to-memory instructions allow operations between a register and a memory location.",
        ),
        bank_question(
            "What is the purpose of the carry flag in a CPU?",
            "Indicates a signed overflow",
            "Indicates an unsigned overflow or borrow",
            "Indicates a zero result",
            "Indicates a parity error",
            "b",
            "The carry flag is set when an arithmetic operation produces a carry out or requires a borrow.",
        ),
    ],
    "COSC205": [
        bank_question(
            "What is the decimal equivalent of the binary number 11011?",
            "23",
            "27",
            "31",
            "25",
            "b",
            "1x16 + 1x8 + 0x4 + 1x2 + 1x1 = 27.",
        ),
        bank_question(
            "Which logic gate outputs 1 only when both inputs are different?",
            "AND",
            "OR",
            "XOR",
            "NAND",
            "c",
            "XOR (exclusive OR) outputs 1 when inputs differ.",
        ),
        bank_question(
            "A 3-to-8 decoder has how many output lines?",
            "3",
            "8",
            "16",
            "4",
            "b",
            "A 3-to-8 decoder has 3 input lines and 2^3 = 8 output lines.",
        ),
        bank_question(
            "Which Boolean algebra law states that A + A' = 1?",
            "Identity law",
            "Complement law",
            "Domination law",
            "Idempotent law",
            "b",
            "The complement law states that a variable ORed with its complement equals 1.",
        ),
        bank_question(
            "A JK flip-flop toggles its output when:",
            "J = 0, K = 0",
            "J = 0, K = 1",
            "J = 1, K = 0",
            "J = 1, K = 1",
            "d",
            "When both J and K are 1, the JK flip-flop toggles its output on each clock pulse.",
        ),
        bank_question(
            "Which gate is known as a universal gate because any Boolean function can be implemented using only this gate?",
            "AND",
            "OR",
            "XOR",
            "NAND",
            "d",
            "NAND gates are universal because any Boolean function can be expressed using only NAND gates.",
        ),
        bank_question(
            "In a multiplexer, the select lines determine:",
            "Which input is routed to the output",
            "The output voltage level",
            "The clock frequency",
            "The power supply connection",
            "a",
            "A multiplexer uses select lines to choose which data input is forwarded to the output.",
        ),
        bank_question(
            "What is the minimum number of NAND gates required to implement a NOT gate?",
            "1",
            "2",
            "3",
            "4",
            "a",
            "A single NAND gate with both inputs tied together acts as an inverter (NOT gate).",
        ),
        bank_question(
            "An SR latch is which type of circuit?",
            "Combinational circuit",
            "Sequential circuit",
            "Arithmetic circuit",
            "Multiplexer circuit",
            "b",
            "An SR latch is a sequential circuit that stores one bit of state.",
        ),
        bank_question(
            "What is the hexadecimal equivalent of the decimal number 255?",
            "FF",
            "F0",
            "E0",
            "0F",
            "a",
            "255 decimal = 11111111 binary = FF hexadecimal.",
        ),
    ],
    "COSC206": [
        bank_question(
            "What does HCI stand for?",
            "Human-Computer Integration",
            "Human-Computer Interaction",
            "High-Capacity Interface",
            "Hardware-Component Interconnect",
            "b",
            "HCI is the study of how people interact with computers and design of user interfaces.",
        ),
        bank_question(
            "Which of the following is an example of a direct manipulation interface?",
            "Command-line interface",
            "Drag-and-drop file management",
            "Batch processing script",
            "Voice-only menu system",
            "b",
            "Drag-and-drop allows users to directly manipulate on-screen objects.",
        ),
        bank_question(
            "Fitts' law predicts that the time to acquire a target depends on:",
            "The colour of the target",
            "The distance to and size of the target",
            "The user's typing speed",
            "The screen resolution",
            "b",
            "Fitts' law states that movement time is a function of distance divided by target width.",
        ),
        bank_question(
            "A heuristic evaluation in HCI is performed by:",
            "End users testing the system",
            "Usability experts inspecting the interface against guidelines",
            "Automated software tools only",
            "Random surveys of the general public",
            "b",
            "Heuristic evaluation involves experts reviewing an interface using established usability principles.",
        ),
        bank_question(
            "What is the primary purpose of a persona in user-centred design?",
            "To replace actual user testing",
            "To create a fictional representative user to guide design decisions",
            "To generate automatic code from sketches",
            "To measure system performance",
            "b",
            "Personas are archetypal users that help designers understand user goals and behaviours.",
        ),
        bank_question(
            "Which of the following is NOT a principle of universal design?",
            "Equitable use",
            "Flexibility in use",
            "Maximum physical effort",
            "Perceptible information",
            "c",
            "Universal design aims to minimise physical effort, not maximise it.",
        ),
        bank_question(
            "The GOMS model stands for:",
            "Goals, Operations, Methods, and Selection rules",
            "General Object Management System",
            "Graphical Output Monitoring Scheme",
            "Goals, Objects, Metrics, and Standards",
            "a",
            "GOMS is a cognitive modelling framework for analysing human performance in HCI.",
        ),
        bank_question(
            "Which colour combination generally provides the best readability on screen?",
            "Red text on blue background",
            "Dark text on light background",
            "Yellow text on white background",
            "Green text on red background",
            "b",
            "High contrast between text and background, such as dark on light, improves readability.",
        ),
        bank_question(
            "What is the main advantage of low-fidelity prototyping?",
            "Fully functional interactive system",
            "Quick and inexpensive feedback early in design",
            "Production-ready code generation",
            "Accurate performance benchmarking",
            "b",
            "Low-fidelity prototypes like paper sketches allow rapid iteration and early usability testing.",
        ),
        bank_question(
            "Which type of memory in the human information-processing model has the shortest duration?",
            "Short-term memory",
            "Long-term memory",
            "Sensory memory",
            "Working memory",
            "c",
            "Sensory memory holds perceptual information for fractions of a second.",
        ),
    ],
    "COSC208": [
        bank_question(
            "Which search algorithm uses a heuristic to estimate the cost from the current state to the goal?",
            "Breadth-first search",
            "Depth-first search",
            "A* search",
            "Random search",
            "c",
            "A* uses a heuristic function h(n) to guide search toward the goal efficiently.",
        ),
        bank_question(
            "In propositional logic, modus ponens states that if P implies Q and P is true, then:",
            "Q is false",
            "Q is true",
            "P is false",
            "P implies Q is false",
            "b",
            "Modus ponens is the inference rule: from P->Q and P, conclude Q.",
        ),
        bank_question(
            "Which knowledge representation method uses frames with slots and fillers?",
            "Semantic networks",
            "Production rules",
            "Frames",
            "Predicate logic",
            "c",
            "Frames represent stereotyped concepts where slots hold attributes and fillers hold values.",
        ),
        bank_question(
            "An expert system consists of which two main components?",
            "Compiler and linker",
            "Knowledge base and inference engine",
            "Database and web server",
            "Monitor and keyboard",
            "b",
            "The knowledge base stores domain facts and rules; the inference engine applies them.",
        ),
        bank_question(
            "What is the primary challenge in natural language processing known as 'word sense disambiguation'?",
            "Identifying parts of speech",
            "Determining which meaning of a word applies in context",
            "Parsing sentence structure",
            "Generating speech from text",
            "b",
            "Word sense disambiguation selects the correct meaning of an ambiguous word based on context.",
        ),
        bank_question(
            "Which algorithm is commonly used for training neural networks?",
            "Gradient descent with backpropagation",
            "Binary search",
            "Merge sort",
            "PageRank",
            "a",
            "Backpropagation computes gradients of the loss function to update neural network weights.",
        ),
        bank_question(
            "The Turing test evaluates:",
            "A machine's processing speed",
            "A machine's ability to exhibit intelligent behaviour indistinguishable from a human",
            "A program's memory usage",
            "The efficiency of a sorting algorithm",
            "b",
            "The Turing test assesses whether a machine can mimic human conversation convincingly.",
        ),
        bank_question(
            "What is the primary purpose of a production rule in an AI system?",
            "To store static data",
            "To represent conditional knowledge in IF-THEN form",
            "To compile source code",
            "To manage memory allocation",
            "b",
            "Production rules encode domain knowledge as condition-action pairs.",
        ),
        bank_question(
            "In computer vision, what is the goal of image segmentation?",
            "To compress the image file size",
            "To partition an image into meaningful regions",
            "To convert colour to grayscale",
            "To rotate the image",
            "b",
            "Image segmentation divides an image into segments for easier analysis.",
        ),
        bank_question(
            "Which type of machine learning uses labelled training data?",
            "Unsupervised learning",
            "Reinforcement learning",
            "Supervised learning",
            "Self-supervised learning",
            "c",
            "Supervised learning trains on input-output pairs with known labels.",
        ),
    ],
    "COSC212": [
        bank_question(
            "Which Java keyword is used to achieve polymorphism through inheritance?",
            "static",
            "final",
            "extends",
            "abstract",
            "c",
            "The extends keyword creates a subclass that can override parent class methods.",
        ),
        bank_question(
            "An interface in Java can contain:",
            "Only abstract methods and constants",
            "Only concrete methods",
            "Instance variables with full implementation",
            "Constructors and destructors",
            "a",
            "Interfaces declare method signatures (abstract) and constant fields.",
        ),
        bank_question(
            "Which data structure operation removes an element from a stack?",
            "enqueue",
            "pop",
            "push",
            "dequeue",
            "b",
            "Pop removes and returns the top element from a stack.",
        ),
        bank_question(
            "What is the time complexity of searching for an element in a balanced binary search tree?",
            "O(1)",
            "O(log n)",
            "O(n)",
            "O(n^2)",
            "b",
            "A balanced BST has O(log n) height, making search logarithmic.",
        ),
        bank_question(
            "Which event-driven programming concept is used to handle button clicks in Java Swing?",
            "ActionListener interface",
            "Runnable interface",
            "Serializable interface",
            "Comparable interface",
            "a",
            "ActionListener defines the actionPerformed method called on button clicks.",
        ),
        bank_question(
            "In Java, what is the purpose of the 'finally' block in exception handling?",
            "To catch exceptions of any type",
            "To execute cleanup code regardless of whether an exception occurs",
            "To throw a new exception",
            "To define custom exception classes",
            "b",
            "The finally block always executes, even if an exception is thrown or caught.",
        ),
        bank_question(
            "Which collection class in Java implements a dynamic array?",
            "LinkedList",
            "ArrayList",
            "HashSet",
            "TreeMap",
            "b",
            "ArrayList provides a resizable array implementation of the List interface.",
        ),
        bank_question(
            "An abstract class in Java:",
            "Can be instantiated directly",
            "Cannot be instantiated and may contain abstract methods",
            "Contains only static methods",
            "Is the same as an interface",
            "b",
            "Abstract classes cannot be instantiated and serve as base classes with partial implementation.",
        ),
        bank_question(
            "Which of the following correctly demonstrates method overloading in Java?",
            "Two methods with same name but different parameters",
            "Two methods with same name in different classes",
            "A method overriding a parent class method",
            "A private method calling a public method",
            "a",
            "Method overloading uses the same method name with different parameter lists.",
        ),
        bank_question(
            "The iterator pattern allows:",
            "Sequential access to elements of a collection without exposing its internal structure",
            "Creating objects without specifying the concrete class",
            "Ensuring only one instance of a class exists",
            "Attaching additional responsibilities to an object dynamically",
            "a",
            "The Iterator pattern provides a standard way to traverse collections.",
        ),
    ],
    "COSC303": [
        bank_question(
            "Which memory technology is typically used for cache memory due to its speed?",
            "DRAM",
            "SRAM",
            "ROM",
            "Flash memory",
            "b",
            "SRAM is faster than DRAM but more expensive, making it ideal for cache.",
        ),
        bank_question(
            "What is the primary benefit of a direct-mapped cache?",
            "Highest hit rate among all cache organisations",
            "Simple and fast lookup with low hardware cost",
            "Fully associative mapping for any block in any location",
            "Set-associative trade-off between cost and performance",
            "b",
            "Direct-mapped cache maps each memory block to exactly one cache line for simple hardware.",
        ),
        bank_question(
            "In pipelining, what is a structural hazard?",
            "When an instruction depends on the result of a previous instruction",
            "When two instructions compete for the same hardware resource",
            "When a branch instruction changes the program flow",
            "When data is not available in the cache",
            "b",
            "Structural hazards occur when hardware resources cannot support all simultaneous pipeline stages.",
        ),
        bank_question(
            "Which floating-point standard is most widely used in modern CPUs?",
            "IEEE 754",
            "ISO 9001",
            "ANSI C99",
            "IEEE 802.11",
            "a",
            "IEEE 754 defines standard formats for single and double precision floating-point arithmetic.",
        ),
        bank_question(
            "What is the function of the memory management unit (MMU)?",
            "Manage file system permissions",
            "Translate virtual addresses to physical addresses",
            "Schedule CPU processes",
            "Control I/O device access",
            "b",
            "The MMU handles address translation from virtual to physical memory.",
        ),
        bank_question(
            "A superscalar processor can:",
            "Execute only one instruction per clock cycle",
            "Execute multiple instructions per clock cycle",
            "Execute instructions only in program order",
            "Execute only integer arithmetic",
            "b",
            "Superscalar architecture allows simultaneous execution of multiple instructions.",
        ),
        bank_question(
            "What is the RISC design philosophy?",
            "Complex instructions that perform multiple operations",
            "Simple, uniform instructions that execute in one clock cycle",
            "Variable-length instructions for compact code",
            "Microprogrammed control for complex operations",
            "b",
            "RISC uses a small set of simple, single-cycle instructions for efficient pipelining.",
        ),
        bank_question(
            "Which cache mapping scheme has the highest flexibility but most complex hardware?",
            "Direct-mapped",
            "Fully associative",
            "Set-associative",
            "Sector mapping",
            "b",
            "Fully associative allows any block to be placed in any cache line but requires complex comparison.",
        ),
        bank_question(
            "Amdahl's law is used to calculate:",
            "Cache hit rate",
            "Maximum speedup from parallelisation given a serial fraction",
            "Pipeline throughput",
            "Memory bandwidth utilisation",
            "b",
            "Amdahl's law states that speedup is limited by the fraction of code that cannot be parallelised.",
        ),
        bank_question(
            "What is the primary advantage of a Harvard architecture over von Neumann architecture?",
            "Single shared memory for instructions and data",
            "Separate memory paths for instructions and data allow simultaneous access",
            "Simpler control unit design",
            "Lower power consumption",
            "b",
            "Harvard architecture uses separate buses and storage for instructions and data.",
        ),
    ],
    "COSC305": [
        bank_question(
            "Which phase of the SDLC involves gathering user requirements?",
            "Implementation",
            "Analysis",
            "Design",
            "Maintenance",
            "b",
            "The analysis phase focuses on understanding and documenting user needs.",
        ),
        bank_question(
            "In UML, what does a use case diagram represent?",
            "The physical network topology",
            "Interactions between actors and the system from a user perspective",
            "The database schema",
            "The internal class implementation",
            "b",
            "Use case diagrams show system functionality from the user's viewpoint.",
        ),
        bank_question(
            "Which UML diagram is best for showing the sequence of messages exchanged between objects?",
            "Class diagram",
            "Sequence diagram",
            "Component diagram",
            "Deployment diagram",
            "b",
            "Sequence diagrams illustrate message ordering over time in an interaction.",
        ),
        bank_question(
            "What is the purpose of a feasibility study?",
            "To write the program code",
            "To determine if a project is technically, economically, and operationally viable",
            "To design the user interface",
            "To test the completed system",
            "b",
            "Feasibility studies assess whether a project should proceed.",
        ),
        bank_question(
            "Which methodology emphasises iterative development and customer collaboration over contract negotiation?",
            "Waterfall model",
            "Agile methodology",
            "Spiral model",
            "V-model",
            "b",
            "Agile methods prioritise working software, customer collaboration, and responding to change.",
        ),
        bank_question(
            "What does CASE stand for in systems analysis?",
            "Computer-Aided Software Engineering",
            "Computer-Assisted System Evaluation",
            "Complex Application Software Environment",
            "Centralised Application System Engine",
            "a",
            "CASE tools support automated software development processes.",
        ),
        bank_question(
            "A context diagram in structured analysis shows:",
            "Detailed internal processes of the system",
            "The system as a single process with external entities and data flows",
            "The database table relationships",
            "The user interface screens",
            "b",
            "A context diagram is the highest-level DFD showing system boundaries.",
        ),
        bank_question(
            "Which UML relationship indicates that one class is a specialised form of another?",
            "Association",
            "Aggregation",
            "Generalisation",
            "Dependency",
            "c",
            "Generalisation (inheritance) indicates an 'is-a' relationship in UML.",
        ),
        bank_question(
            "What is the primary goal of the testing phase?",
            "To design the system architecture",
            "To identify defects and verify the system meets requirements",
            "To deploy the system to production",
            "To gather performance metrics",
            "b",
            "Testing aims to find bugs and confirm the system matches its specification.",
        ),
        bank_question(
            "Which document formally defines the scope, objectives, and constraints of a software project?",
            "User manual",
            "Software requirements specification (SRS)",
            "Test plan",
            "Code review report",
            "b",
            "The SRS documents functional and non-functional requirements of the software.",
        ),
    ],
    "COSC311": [
        bank_question(
            "Which paradigm treats computation as the evaluation of mathematical functions and avoids mutable state?",
            "Imperative programming",
            "Object-oriented programming",
            "Functional programming",
            "Logic programming",
            "c",
            "Functional programming uses pure functions and immutable data.",
        ),
        bank_question(
            "In Prolog, a query '?- parent(X, Y)' is an example of:",
            "Imperative command",
            "Logic programming query using unification",
            "Object instantiation",
            "Function call",
            "b",
            "Prolog uses logical queries to find values that satisfy the given predicates.",
        ),
        bank_question(
            "Which scoping rule means a variable refers to the most recently declared binding in the lexical context?",
            "Dynamic scoping",
            "Static (lexical) scoping",
            "Global scoping",
            "Local scoping",
            "b",
            "Static scoping resolves variable references based on the program's textual structure.",
        ),
        bank_question(
            "A closure is a function that:",
            "Has no parameters",
            "Captures and preserves the lexical environment in which it was defined",
            "Cannot be passed as an argument",
            "Must be defined in the global scope",
            "b",
            "A closure bundles a function with its referencing environment.",
        ),
        bank_question(
            "Which of the following is a purely functional programming language?",
            "Java",
            "C++",
            "Haskell",
            "Python",
            "c",
            "Haskell is a purely functional language with no mutable state by default.",
        ),
        bank_question(
            "What is the purpose of a type system in programming languages?",
            "To optimise compile time only",
            "To detect and prevent type errors during compilation or runtime",
            "To generate documentation automatically",
            "To manage memory allocation",
            "b",
            "Type systems enforce correct usage of data types to catch errors.",
        ),
        bank_question(
            "In logic programming, what is a Horn clause?",
            "A clause with at most one positive literal",
            "A clause with exactly two literals",
            "A clause with no variables",
            "A clause that is always true",
            "a",
            "Horn clauses contain at most one positive literal and form the basis of Prolog.",
        ),
        bank_question(
            "Which parameter passing mechanism evaluates arguments before the function call?",
            "Call by name",
            "Call by need",
            "Call by value",
            "Lazy evaluation",
            "c",
            "Call by value evaluates the argument expression and passes the result.",
        ),
        bank_question(
            "What distinguishes a compiled language from an interpreted language?",
            "Compiled languages are always slower than interpreted ones",
            "Compiled languages translate source code to machine code before execution",
            "Interpreted languages cannot use variables",
            "Compiled languages do not support functions",
            "b",
            "Compilation translates the entire source program before execution.",
        ),
        bank_question(
            "Exception handling in programming languages is a form of:",
            "Sequential control flow",
            "Structured non-local transfer of control",
            "Loop iteration",
            "Conditional branching",
            "b",
            "Exception handling provides structured ways to transfer control when errors occur.",
        ),
    ],
    "COSC401": [
        bank_question(
            "Which notation is used to describe the asymptotic upper bound of an algorithm's running time?",
            "Big-O notation",
            "Big-Omega notation",
            "Big-Theta notation",
            "Little-O notation",
            "a",
            "Big-O notation (O) provides an asymptotic upper bound on growth rate.",
        ),
        bank_question(
            "The time complexity of merge sort in the worst case is:",
            "O(n)",
            "O(n log n)",
            "O(n^2)",
            "O(log n)",
            "b",
            "Merge sort divides the array in half at each step, giving O(n log n) worst-case time.",
        ),
        bank_question(
            "Which algorithm design technique solves problems by breaking them into overlapping subproblems?",
            "Divide and conquer",
            "Dynamic programming",
            "Greedy algorithm",
            "Brute force",
            "b",
            "Dynamic programming solves overlapping subproblems and stores results to avoid recomputation.",
        ),
        bank_question(
            "The greedy algorithm for the coin change problem always produces an optimal solution for:",
            "Any coin system",
            "Canonical coin systems only",
            "No coin system",
            "Only US currency",
            "b",
            "Greedy works optimally only when the coin system is canonical.",
        ),
        bank_question(
            "The Knapsack problem is an example of which class of problems?",
            "P",
            "NP-complete",
            "NP-hard",
            "Undecidable",
            "b",
            "The 0/1 Knapsack problem is NP-complete.",
        ),
        bank_question(
            "Which of the following is NOT a characteristic of NP-complete problems?",
            "Verifiable in polynomial time",
            "Solvable in polynomial time",
            "Reducible to any other NP-complete problem in polynomial time",
            "Hard to solve efficiently in general",
            "b",
            "NP-complete problems are not known to be solvable in polynomial time.",
        ),
        bank_question(
            "What is the time complexity of binary search?",
            "O(1)",
            "O(log n)",
            "O(n)",
            "O(n log n)",
            "b",
            "Binary search halves the search space each iteration, giving logarithmic time.",
        ),
        bank_question(
            "In the divide-and-conquer paradigm, the 'combine' step:",
            "Divides the problem into smaller subproblems",
            "Merges the solutions of subproblems to form the overall solution",
            "Selects the best candidate at each step",
            "Recursively calls the base case",
            "b",
            "The combine step assembles subproblem solutions into the final answer.",
        ),
        bank_question(
            "Which of the following is an approximation algorithm?",
            "Binary search",
            "The vertex cover approximation guaranteeing at most twice optimal",
            "Bubble sort",
            "Breadth-first search",
            "b",
            "Approximation algorithms provide near-optimal solutions for hard problems.",
        ),
        bank_question(
            "The Master Theorem is used to solve recurrences of which form?",
            "T(n) = aT(n/b) + f(n)",
            "T(n) = T(n-1) + n",
            "T(n) = T(n/2) + T(n/2) + 1",
            "T(n) = nT(n-1)",
            "a",
            "The Master Theorem applies to divide-and-conquer recurrences of the form T(n) = aT(n/b) + f(n).",
        ),
    ],
    "COSC402": [
        bank_question(
            "What is the Z notation primarily used for?",
            "Object-oriented programming",
            "Formal software specification using mathematical notation",
            "Database querying",
            "Web application development",
            "b",
            "Z is a formal specification language based on set theory and predicate logic.",
        ),
        bank_question(
            "In formal methods, a Hoare triple {P} C {Q} means:",
            "If precondition P holds before executing command C, then postcondition Q holds afterwards",
            "Command C modifies both P and Q",
            "P and Q are equivalent statements",
            "C is executed repeatedly until P equals Q",
            "a",
            "A Hoare triple formalises the semantics of program correctness.",
        ),
        bank_question(
            "Which of the following is a formal language for specifying syntax?",
            "UML",
            "BNF (Backus-Naur Form)",
            "HTML",
            "SQL",
            "b",
            "BNF is a formal notation for describing the syntax of context-free languages.",
        ),
        bank_question(
            "Model checking is a technique for:",
            "Verifying that a system model satisfies given temporal logic properties",
            "Compiling source code to machine code",
            "Designing user interfaces",
            "Managing software project schedules",
            "a",
            "Model checking exhaustively checks all states of a system model against specifications.",
        ),
        bank_question(
            "What is a finite state machine (FSM)?",
            "A model with a finite number of states and transitions between them",
            "A machine that never halts",
            "A database with unlimited records",
            "A network protocol for infinite data streams",
            "a",
            "An FSM consists of a finite set of states, transitions, and an initial state.",
        ),
        bank_question(
            "In VDM, what is a 'retrieve function' used for?",
            "To fetch data from a database",
            "To relate an abstract specification to a concrete implementation",
            "To retrieve deleted files",
            "To manage memory allocation",
            "b",
            "Retrieve functions map concrete states to their abstract counterparts in VDM.",
        ),
        bank_question(
            "Which of the following is a temporal logic used in formal verification?",
            "First-order logic",
            "Linear Temporal Logic (LTL)",
            "Propositional logic",
            "Description logic",
            "b",
            "LTL adds temporal operators like 'always' and 'eventually' for reasoning over time.",
        ),
        bank_question(
            "Invariant analysis in formal methods checks that:",
            "A property holds at all times during execution",
            "The program compiles without errors",
            "The user interface is attractive",
            "The database connection is active",
            "a",
            "An invariant is a condition that must always be true at certain points in execution.",
        ),
        bank_question(
            "What is the difference between verification and validation?",
            "Verification checks if the product is built correctly; validation checks if the right product is built",
            "They are the same thing",
            "Validation is about syntax; verification is about semantics",
            "Verification is done by users; validation is done by developers",
            "a",
            "Verification ensures correctness against specification; validation ensures user needs are met.",
        ),
        bank_question(
            "Which formal method is based on communicating sequential processes?",
            "Z notation",
            "CSP (Communicating Sequential Processes)",
            "VDM",
            "Alloy",
            "b",
            "CSP is a formal language for describing patterns of interaction in concurrent systems.",
        ),
    ],
    "COSC403": [
        bank_question(
            "Which software process model emphasises risk analysis at each iteration?",
            "Waterfall model",
            "Spiral model",
            "V-model",
            "Agile model",
            "b",
            "The spiral model combines iterative development with systematic risk assessment.",
        ),
        bank_question(
            "What is the primary purpose of design patterns?",
            "To eliminate the need for testing",
            "To provide reusable solutions to commonly occurring design problems",
            "To replace programming languages",
            "To automatically generate documentation",
            "b",
            "Design patterns capture proven solutions to recurring design problems.",
        ),
        bank_question(
            "Which design pattern ensures a class has only one instance?",
            "Factory Method",
            "Singleton",
            "Observer",
            "Strategy",
            "b",
            "The Singleton pattern restricts instantiation of a class to one object.",
        ),
        bank_question(
            "What does coupling measure in software design?",
            "How closely related the responsibilities of a module are",
            "The degree of interdependence between modules",
            "The number of lines of code in a module",
            "The speed of program execution",
            "b",
            "Coupling measures how much one module depends on another.",
        ),
        bank_question(
            "The Observer pattern is best suited for:",
            "Creating objects without specifying their concrete classes",
            "Defining a one-to-many dependency so that when one object changes, all dependents are notified",
            "Encapsulating a request as an object",
            "Providing a simplified interface to a complex subsystem",
            "b",
            "The Observer pattern implements publish-subscribe semantics.",
        ),
        bank_question(
            "What is the main goal of refactoring?",
            "Adding new features to the software",
            "Improving internal structure without changing external behaviour",
            "Rewriting the system in a different language",
            "Deploying the software to production",
            "b",
            "Refactoring improves code readability, maintainability, and design without altering behaviour.",
        ),
        bank_question(
            "Which architectural pattern organises an application into three interconnected parts?",
            "Model-View-Controller (MVC)",
            "Pipe and filter",
            "Blackboard",
            "Layered architecture",
            "a",
            "MVC separates concerns into model (data), view (UI), and controller (logic).",
        ),
        bank_question(
            "In software engineering, 'cohesion' refers to:",
            "The degree to which elements within a module belong together",
            "The number of modules in a system",
            "The size of the user interface",
            "The speed of the network connection",
            "a",
            "High cohesion means a module has focused, closely related responsibilities.",
        ),
        bank_question(
            "Which UML diagram is used to model the static structure of a system?",
            "Use case diagram",
            "Sequence diagram",
            "Class diagram",
            "Activity diagram",
            "c",
            "Class diagrams show classes, attributes, methods, and relationships.",
        ),
        bank_question(
            "The principle of information hiding suggests that:",
            "All data should be globally accessible",
            "Module internals should be hidden behind a stable interface",
            "Documentation should not be shared with users",
            "Source code should be encrypted",
            "b",
            "Information hiding protects internal implementation details from external access.",
        ),
    ],
    "COSC404": [
        bank_question(
            "Which protocol is used for network management and monitoring?",
            "HTTP",
            "SNMP",
            "FTP",
            "SMTP",
            "b",
            "SNMP (Simple Network Management Protocol) is used to manage and monitor network devices.",
        ),
        bank_question(
            "What is the function of RMON in network management?",
            "Routing packets between networks",
            "Remote monitoring of network segments and traffic statistics",
            "Encrypting network communications",
            "Assigning IP addresses dynamically",
            "b",
            "RMON (Remote Monitoring) provides network traffic monitoring and analysis.",
        ),
        bank_question(
            "Which of the following is a network management functional area defined by OSI?",
            "Performance management",
            "File management",
            "Memory management",
            "Process management",
            "a",
            "OSI network management includes fault, configuration, accounting, performance, and security (FCAPS).",
        ),
        bank_question(
            "The MIB (Management Information Base) is:",
            "A routing algorithm",
            "A database of managed objects accessible via SNMP",
            "A type of network cable",
            "A network topology",
            "b",
            "MIB defines a hierarchical collection of network management information.",
        ),
        bank_question(
            "What is the purpose of network segmentation?",
            "To increase network speed by adding more cables",
            "To divide a network into smaller parts to improve performance and security",
            "To eliminate all network devices",
            "To merge multiple networks into one",
            "b",
            "Network segmentation divides a network into smaller segments to contain traffic and improve security.",
        ),
        bank_question(
            "Which tool is commonly used to measure network bandwidth utilisation?",
            "Wireshark",
            "Microsoft Word",
            "Adobe Photoshop",
            "Visual Studio Code",
            "a",
            "Wireshark captures and analyses network packets to measure utilisation.",
        ),
        bank_question(
            "What does 'fault management' in network management involve?",
            "Detecting, isolating, and correcting network problems",
            "Designing network topologies",
            "Installing network cables",
            "Updating software applications",
            "a",
            "Fault management deals with identifying and resolving network failures.",
        ),
        bank_question(
            "Which configuration management task involves tracking changes to network device settings?",
            "Change management",
            "Asset management",
            "Capacity management",
            "Security management",
            "a",
            "Change management tracks and controls modifications to network device configurations.",
        ),
        bank_question(
            "What is the role of a network operations centre (NOC)?",
            "Developing software applications",
            "Centralised monitoring and management of network infrastructure",
            "Designing web pages",
            "Teaching networking courses",
            "b",
            "A NOC serves as the central hub for network monitoring and incident response.",
        ),
        bank_question(
            "Which protocol provides a secure method for remote network device configuration?",
            "Telnet",
            "SSH",
            "FTP",
            "HTTP",
            "b",
            "SSH (Secure Shell) encrypts remote session traffic, unlike Telnet.",
        ),
    ],
    "COSC405": [
        bank_question(
            "Which technology is commonly used for server-side web application development?",
            "HTML",
            "CSS",
            "ASP.NET",
            "JavaScript (client-side only)",
            "c",
            "ASP.NET is a server-side framework for building dynamic web applications.",
        ),
        bank_question(
            "What is the purpose of session management in web applications?",
            "To store stylesheets",
            "To maintain state across multiple HTTP requests from the same user",
            "To compress images",
            "To validate email addresses",
            "b",
            "HTTP is stateless; sessions provide continuity by storing user-specific data across requests.",
        ),
        bank_question(
            "Which of the following is a server-side programming language?",
            "HTML",
            "CSS",
            "PHP",
            "JavaScript (client-side)",
            "c",
            "PHP executes on the web server to generate dynamic content.",
        ),
        bank_question(
            "What is the purpose of input validation in web applications?",
            "To make web pages look attractive",
            "To ensure user input meets expected format and security constraints",
            "To increase page load speed",
            "To add animations to forms",
            "b",
            "Input validation prevents malformed or malicious data from compromising the application.",
        ),
        bank_question(
            "Which HTTP method is typically used for submitting form data?",
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "b",
            "POST sends form data in the request body and is suitable for submissions that change state.",
        ),
        bank_question(
            "What is SQL injection?",
            "A technique to optimise database queries",
            "An attack that inserts malicious SQL code into application queries",
            "A method for indexing database tables",
            "A way to create database backups",
            "b",
            "SQL injection exploits unsanitised user input to manipulate database queries.",
        ),
        bank_question(
            "Which markup language is used to create web pages?",
            "XML",
            "HTML",
            "YAML",
            "JSON",
            "b",
            "HTML (HyperText Markup Language) structures content on the web.",
        ),
        bank_question(
            "What is the role of a web server in web application architecture?",
            "To render graphics on the client side",
            "To accept HTTP requests and serve responses, often running application code",
            "To manage the operating system",
            "To compile source code",
            "b",
            "Web servers like Apache or Nginx handle HTTP communication and execute server-side logic.",
        ),
        bank_question(
            "What does a cookie store in web applications?",
            "The entire web page content",
            "Small pieces of data on the client side for state management",
            "The server's source code",
            "The database schema",
            "b",
            "Cookies are small text files stored by the browser for session tracking and personalisation.",
        ),
        bank_question(
            "Which technology allows web pages to update content dynamically without reloading?",
            "AJAX",
            "FTP",
            "SMTP",
            "TCP",
            "a",
            "AJAX (Asynchronous JavaScript and XML) enables partial page updates via background requests.",
        ),
    ],
    "COSC406": [
        bank_question(
            "Which concurrency control technique ensures that transactions appear to execute in isolation?",
            "Serialisability",
            "Lock-based protocols",
            "Timestamp ordering",
            "All of the above",
            "d",
            "Serialisability through locking, timestamps, or optimistic methods ensures isolation.",
        ),
        bank_question(
            "In a distributed database, the CAP theorem states that a system can guarantee at most:",
            "Consistency, availability, and partition tolerance simultaneously",
            "Exactly two of consistency, availability, and partition tolerance",
            "Only consistency and availability",
            "Only partition tolerance and consistency",
            "b",
            "The CAP theorem states a distributed system cannot guarantee all three simultaneously.",
        ),
        bank_question(
            "Which advanced data model represents data as collections of objects with attributes and methods?",
            "Relational model",
            "Object-oriented database model",
            "Hierarchical model",
            "Network model",
            "b",
            "Object-oriented databases store objects directly, similar to OOP languages.",
        ),
        bank_question(
            "What is the purpose of a write-ahead log in database recovery?",
            "To reduce storage space",
            "To ensure durability by recording changes before they are applied",
            "To encrypt sensitive data",
            "To optimise query performance",
            "b",
            "Write-ahead logging ensures that transaction logs are written to stable storage before data files.",
        ),
        bank_question(
            "Which type of failure occurs when a transaction must be aborted due to a logical error?",
            "System failure",
            "Transaction failure",
            "Media failure",
            "Network failure",
            "b",
            "Transaction failures include logical errors, integrity violations, or deadlocks.",
        ),
        bank_question(
            "In query optimisation, which join method uses an index to find matching tuples?",
            "Nested loop join",
            "Index nested loop join",
            "Sort-merge join",
            "Hash join",
            "b",
            "Index nested loop join leverages an existing index to speed up join operations.",
        ),
        bank_question(
            "Which technique is used to recover from media failures in database systems?",
            "Transaction rollback",
            "Log-based recovery and backup restoration",
            "Deadlock detection",
            "Query optimisation",
            "b",
            "Media failure recovery typically involves restoring from a backup and reapplying the log.",
        ),
        bank_question(
            "What is the ACID property 'Durability' in database transactions?",
            "Transactions appear to execute in isolation",
            "Once committed, a transaction's changes persist despite failures",
            "All operations in a transaction complete or none do",
            "Transactions preserve database consistency",
            "b",
            "Durability guarantees that committed changes survive subsequent failures.",
        ),
        bank_question(
            "Which concurrency problem occurs when a transaction reads a value written by an uncommitted transaction?",
            "Lost update",
            "Dirty read",
            "Phantom read",
            "Non-repeatable read",
            "b",
            "A dirty read occurs when data from an uncommitted transaction is read.",
        ),
        bank_question(
            "In a distributed database, horizontal fragmentation divides:",
            "A table by rows across multiple sites",
            "A table by columns across multiple sites",
            "The database schema into separate databases",
            "The query into subqueries",
            "a",
            "Horizontal fragmentation distributes rows of a relation across different locations.",
        ),
    ],
    "COSC407": [
        bank_question(
            "Which layer of the OSI model is responsible for routing packets across networks?",
            "Data link layer",
            "Network layer",
            "Transport layer",
            "Application layer",
            "b",
            "The network layer handles logical addressing and routing between different networks.",
        ),
        bank_question(
            "What does TCP stand for?",
            "Transmission Control Protocol",
            "Transport Communication Protocol",
            "Transfer Control Procedure",
            "Technical Connection Protocol",
            "a",
            "TCP is a connection-oriented transport protocol providing reliable data delivery.",
        ),
        bank_question(
            "Which device operates at the data link layer of the OSI model?",
            "Router",
            "Switch",
            "Hub",
            "Modem",
            "b",
            "Switches forward frames based on MAC addresses at the data link layer.",
        ),
        bank_question(
            "What is the purpose of DNS in computer networks?",
            "To assign IP addresses dynamically",
            "To translate domain names to IP addresses",
            "To encrypt network traffic",
            "To manage network users",
            "b",
            "The Domain Name System maps human-readable hostnames to numerical IP addresses.",
        ),
        bank_question(
            "Which topology connects all devices in a closed loop?",
            "Star topology",
            "Bus topology",
            "Ring topology",
            "Mesh topology",
            "c",
            "In a ring topology, each device connects to exactly two neighbours forming a circular path.",
        ),
        bank_question(
            "What is the maximum segment length for 100BASE-TX Ethernet?",
            "100 metres",
            "185 metres",
            "500 metres",
            "200 metres",
            "a",
            "100BASE-TX (Fast Ethernet) has a maximum segment length of 100 metres.",
        ),
        bank_question(
            "Which protocol provides reliable, ordered delivery of a stream of bytes?",
            "UDP",
            "TCP",
            "IP",
            "ICMP",
            "b",
            "TCP provides reliable, in-order delivery with error checking and flow control.",
        ),
        bank_question(
            "What is subnet masking used for?",
            "To hide network traffic from unauthorised users",
            "To determine which part of an IP address identifies the network and which identifies the host",
            "To compress data for transmission",
            "To assign MAC addresses to devices",
            "b",
            "A subnet mask separates the network prefix from the host identifier in an IP address.",
        ),
        bank_question(
            "Which class of IP address has a default subnet mask of 255.0.0.0?",
            "Class A",
            "Class B",
            "Class C",
            "Class D",
            "a",
            "Class A addresses use the first octet for network ID and have subnet mask 255.0.0.0.",
        ),
        bank_question(
            "What is CSMA/CD used for in Ethernet networks?",
            "Error correction in fibre optic cables",
            "Collision detection in shared media",
            "Encrypting data frames",
            "Assigning IP addresses",
            "b",
            "Carrier Sense Multiple Access with Collision Detection handles contention on shared Ethernet segments.",
        ),
    ],
    "COSC408": [
        bank_question(
            "Which phase of a compiler performs lexical analysis?",
            "Syntax analysis",
            "Semantic analysis",
            "Lexical analysis (scanning)",
            "Code generation",
            "c",
            "The scanner or lexer breaks source code into tokens.",
        ),
        bank_question(
            "What is a context-free grammar used for in compiler design?",
            "To define the lexical structure of tokens",
            "To describe the syntax (grammar) of a programming language",
            "To perform type checking",
            "To generate machine code",
            "b",
            "Context-free grammars define the syntactic structure of programming languages.",
        ),
        bank_question(
            "Which parser construction method builds the parse tree from leaves to root?",
            "Top-down parsing",
            "Bottom-up parsing",
            "Recursive descent parsing",
            "LL parsing",
            "b",
            "Bottom-up parsers (e.g., LR parsers) construct the parse tree starting from the input tokens.",
        ),
        bank_question(
            "What is the main purpose of a symbol table in a compiler?",
            "To store the source code text",
            "To record information about identifiers, their types, and scopes",
            "To hold the generated machine code",
            "To manage compiler memory allocation",
            "b",
            "The symbol table stores and retrieves information about program identifiers.",
        ),
        bank_question(
            "Which compiler phase generates intermediate representation from the parse tree?",
            "Lexical analysis",
            "Syntax analysis",
            "Semantic analysis and intermediate code generation",
            "Code optimisation",
            "c",
            "Semantic analysis checks types and produces intermediate code like three-address code.",
        ),
        bank_question(
            "What is the function of a loader in the compilation process?",
            "To translate assembly code to machine code",
            "To load the executable program into memory and prepare it for execution",
            "To optimise the generated code",
            "To check for syntax errors",
            "b",
            "The loader loads executable code into memory, resolves addresses, and starts execution.",
        ),
        bank_question(
            "Which optimisation technique moves loop-invariant computations outside the loop?",
            "Constant folding",
            "Loop-invariant code motion",
            "Dead code elimination",
            "Strength reduction",
            "b",
            "Loop-invariant code motion hoists operations that produce the same result each iteration.",
        ),
        bank_question(
            "What is the difference between a compiler and an interpreter?",
            "Compilers produce errors; interpreters do not",
            "A compiler translates the entire program before execution; an interpreter executes line by line",
            "Compilers are slower than interpreters",
            "Interpreters produce machine code; compilers do not",
            "b",
            "Compilers translate source code to executable code in advance; interpreters execute directly.",
        ),
        bank_question(
            "Which parsing technique is most suitable for handling operator precedence?",
            "Recursive descent with precedence climbing",
            "LL(1) parsing",
            "LR parsing with precedence and associativity rules",
            "Simple precedence parsing",
            "c",
            "LR parsers can handle operator precedence naturally through grammar rules.",
        ),
        bank_question(
            "What is register allocation in code optimisation?",
            "Assigning symbolic variables to physical CPU registers",
            "Allocating memory for arrays",
            "Managing disk I/O operations",
            "Scheduling instruction execution order",
            "a",
            "Register allocation maps program variables to limited CPU registers for fast access.",
        ),
    ],
    "COSC409": [
        bank_question(
            "Which law governs the protection of personal data in computing systems?",
            "Copyright law",
            "Data protection law",
            "Contract law",
            "Patent law",
            "b",
            "Data protection law regulates how personal information is collected, stored, and processed.",
        ),
        bank_question(
            "What is the primary purpose of copyright in computing?",
            "To protect inventions",
            "To protect original works of authorship including software code",
            "To protect business names and logos",
            "To protect trade secrets",
            "b",
            "Copyright protects original creative works, including computer programs.",
        ),
        bank_question(
            "Which of the following is a form of intellectual property that protects inventions?",
            "Copyright",
            "Trademark",
            "Patent",
            "Trade secret",
            "c",
            "Patents protect novel, useful, and non-obvious inventions for a limited period.",
        ),
        bank_question(
            "What is the Computer Misuse Act primarily concerned with?",
            "Regulating internet speeds",
            "Criminalising unauthorised access to computer systems and data",
            "Setting software licensing standards",
            "Establishing computer hardware specifications",
            "b",
            "The Computer Misuse Act addresses hacking, unauthorised access, and related cybercrimes.",
        ),
        bank_question(
            "What does the ACM Code of Ethics require of computing professionals?",
            "Maximising profit for their employer",
            "Prioritising public interest, honesty, and professional responsibility",
            "Keeping all technical knowledge secret",
            "Avoiding collaboration with other professionals",
            "b",
            "The ACM Code of Ethics emphasises the public good, honesty, and professional excellence.",
        ),
        bank_question(
            "Which term describes the right of individuals to control access to their personal information?",
            "Security",
            "Privacy",
            "Anonymity",
            "Confidentiality",
            "b",
            "Privacy concerns the right to control one's own personal data.",
        ),
        bank_question(
            "What is a digital signature used for?",
            "Encrypting large files",
            "Verifying the authenticity and integrity of digital messages or documents",
            "Creating animated graphics",
            "Managing database connections",
            "b",
            "Digital signatures provide authentication, non-repudiation, and integrity.",
        ),
        bank_question(
            "Which ethical framework evaluates actions based on their consequences?",
            "Deontological ethics",
            "Utilitarianism",
            "Virtue ethics",
            "Rights-based ethics",
            "b",
            "Utilitarianism judges actions by their outcomes, aiming to maximise overall good.",
        ),
        bank_question(
            "What is the primary concern of 'digital divide'?",
            "Differences in internet speeds between countries",
            "Inequality in access to information and communication technologies",
            "The gap between different programming languages",
            "Differences in computer hardware prices",
            "b",
            "The digital divide refers to unequal access to technology and digital literacy.",
        ),
        bank_question(
            "Whistle-blowing in a computing context involves:",
            "Reporting unethical or illegal activities within an organisation",
            "Testing software performance",
            "Designing new algorithms",
            "Managing project budgets",
            "a",
            "Whistle-blowing is the disclosure of wrongdoing to authorities or the public.",
        ),
    ],
    "COSC413": [
        bank_question(
            "Computational science involves using computers to:",
            "Browse the internet",
            "Solve complex scientific and engineering problems through simulation",
            "Create word processing documents",
            "Manage email communications",
            "b",
            "Computational science uses simulation and modelling to study scientific problems.",
        ),
        bank_question(
            "Which parallel computing architecture uses shared memory?",
            "Distributed memory systems",
            "Symmetric multiprocessing (SMP)",
            "Cluster computing",
            "Grid computing",
            "b",
            "SMP systems have multiple processors sharing a single memory address space.",
        ),
        bank_question(
            "What is scientific visualisation primarily used for?",
            "Creating artistic graphics",
            "Representing complex scientific data visually for analysis and insight",
            "Editing digital photographs",
            "Designing user interfaces",
            "b",
            "Scientific visualisation transforms data into visual representations for understanding.",
        ),
        bank_question(
            "Which of the following is a parallel programming standard?",
            "SQL",
            "MPI (Message Passing Interface)",
            "HTML",
            "CSS",
            "b",
            "MPI is a standard for message-passing in parallel computing.",
        ),
        bank_question(
            "What is the main advantage of parallel computing?",
            "Simpler program design",
            "Reduced execution time by performing multiple operations simultaneously",
            "Lower hardware cost",
            "Easier debugging",
            "b",
            "Parallel computing divides work across multiple processors to speed up computation.",
        ),
        bank_question(
            "Which type of memory system is critical for high-performance computing?",
            "Single-level cache only",
            "Hierarchical memory including registers, cache, main memory, and disk",
            "Only main memory",
            "Only disk storage",
            "b",
            "HPC systems use a hierarchy of memory types to balance speed and capacity.",
        ),
        bank_question(
            "What is pipelining in the context of high-performance computing?",
            "A technique to overlap instruction execution for increased throughput",
            "A method for sorting data",
            "A network routing protocol",
            "A database indexing technique",
            "a",
            "Pipelining divides instruction execution into stages that operate in parallel.",
        ),
        bank_question(
            "Which of the following is a metric for evaluating parallel algorithm performance?",
            "Lines of code",
            "Speedup and efficiency",
            "Number of functions",
            "Memory used by variables",
            "b",
            "Speedup measures the ratio of sequential to parallel execution time.",
        ),
        bank_question(
            "GPU computing is particularly effective for:",
            "Sequential file processing",
            "Data-parallel workloads with many arithmetic operations",
            "Single-threaded applications",
            "User interface design",
            "b",
            "GPUs excel at data-parallel computations with many floating-point operations.",
        ),
        bank_question(
            "Which file format is commonly used for storing large scientific datasets?",
            "DOCX",
            "HDF5 (Hierarchical Data Format)",
            "XLSX",
            "PDF",
            "b",
            "HDF5 is designed for storing and organising large amounts of scientific data.",
        ),
    ],
    "COSC416": [
        bank_question(
            "What is the primary purpose of discrete-event simulation?",
            "To model systems where state changes occur at discrete points in time",
            "To analyse continuous physical processes",
            "To compile computer programs",
            "To design user interfaces",
            "a",
            "Discrete-event simulation models systems whose state changes at specific event times.",
        ),
        bank_question(
            "Which distribution is commonly used to model inter-arrival times in queuing systems?",
            "Normal distribution",
            "Uniform distribution",
            "Exponential distribution",
            "Binomial distribution",
            "c",
            "The exponential distribution models time between independent random events.",
        ),
        bank_question(
            "What is a pseudo-random number generator used for in simulation?",
            "To generate truly unpredictable numbers",
            "To produce a deterministic sequence of numbers that appear random",
            "To sort simulation data",
            "To encrypt simulation results",
            "b",
            "PRNGs produce reproducible sequences that pass statistical randomness tests.",
        ),
        bank_question(
            "Which technique is used to validate a simulation model?",
            "Comparing model outputs with real system data",
            "Making the model as complex as possible",
            "Ignoring all input parameters",
            "Running the simulation only once",
            "a",
            "Validation checks whether the model accurately represents the real system.",
        ),
        bank_question(
            "What is the significance of the seed value in a random number generator?",
            "It determines the speed of generation",
            "It initialises the generator, allowing reproducible simulation runs",
            "It encrypts the output",
            "It controls the output format",
            "b",
            "The same seed produces identical random sequences for reproducible experiments.",
        ),
        bank_question(
            "In queuing theory, what does M/M/1 represent?",
            "A queue with Poisson arrivals, exponential service times, and one server",
            "A queue with deterministic arrivals and service",
            "A queue with multiple servers and general service times",
            "A queue with finite buffer capacity",
            "a",
            "M/M/1 denotes Markovian (memoryless) arrivals and service with a single server.",
        ),
        bank_question(
            "What is the goal of output analysis in simulation?",
            "To design the simulation model",
            "To interpret simulation results and draw valid conclusions",
            "To generate random numbers",
            "To visualise the simulation",
            "b",
            "Output analysis uses statistical methods to make inferences from simulation data.",
        ),
        bank_question(
            "Which simulation language was developed specifically for discrete-event simulation?",
            "Java",
            "GPSS (General Purpose Simulation System)",
            "Python",
            "C++",
            "b",
            "GPSS is a specialised simulation language for discrete-event modelling.",
        ),
        bank_question(
            "What is the purpose of terminating conditions in a simulation?",
            "To define when the simulation run should end",
            "To set the simulation speed",
            "To configure the output format",
            "To initialise the model parameters",
            "a",
            "Terminating conditions specify the stopping criterion for a simulation run.",
        ),
        bank_question(
            "Which statistical test is used to evaluate whether a random number sequence is uniformly distributed?",
            "t-test",
            "Chi-squared goodness-of-fit test",
            "ANOVA",
            "F-test",
            "b",
            "The chi-squared test compares observed frequencies with expected uniform distribution.",
        ),
    ],
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
SessionDep = Annotated[Session, Depends(get_db)]


def hash_password(password: str) -> str:
    iterations = 260_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        ).hex()
        return hmac.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user.id), "role": user.role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def generate_research_id(db: Session) -> str:
    year = datetime.utcnow().year
    while True:
        candidate = f"ABU-CS-{year}-{secrets.randbelow(9000) + 1000}"
        exists = db.scalar(select(User.id).where(User.research_id == candidate))
        if not exists:
            return candidate


def normalized_email(email: str) -> str:
    return email.strip().lower()


def log_activity(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    metadata: dict | None = None,
) -> ActivityLog:
    event = ActivityLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(event)
    return event


def get_current_user(db: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_researcher(user: CurrentUser) -> User:
    if user.role not in RESEARCH_ROLES:
        raise HTTPException(status_code=403, detail="Researcher or admin access is required.")
    return user


def require_content_manager(user: CurrentUser) -> User:
    if user.role not in CONTENT_ROLES:
        raise HTTPException(status_code=403, detail="Facilitator, researcher, or admin access is required.")
    return user


ResearcherUser = Annotated[User, Depends(require_researcher)]
ContentManagerUser = Annotated[User, Depends(require_content_manager)]


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "research_id": user.research_id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "study_group": user.study_group,
        "programme": user.programme,
        "department": user.department,
        "level": user.level,
        "interests": user.interests,
        "created_at": user.created_at,
    }


def serialize_course(topic: Topic) -> dict:
    return {
        "id": topic.id,
        "title": topic.title,
        "code": topic.code,
        "description": topic.description,
        "facilitator": topic.facilitator,
        "created_at": topic.created_at,
        "member_count": len(topic.memberships),
        "resource_count": len(topic.resources),
        "discussion_count": len(topic.threads),
    }


def serialize_resource(resource: Resource) -> dict:
    ratings = [feedback.usefulness_rating for feedback in resource.feedback]
    average_usefulness = round(sum(ratings) / len(ratings), 2) if ratings else None
    return {
        "id": resource.id,
        "course_id": resource.course_id,
        "title": resource.title,
        "resource_type": resource.resource_type,
        "difficulty": resource.difficulty,
        "estimated_minutes": resource.estimated_minutes,
        "url": resource.url,
        "body": resource.body,
        "created_at": resource.created_at,
        "average_usefulness": average_usefulness,
        "view_count": len(resource.views),
    }


def serialize_reply(reply: DiscussionReply) -> dict:
    return {
        "id": reply.id,
        "thread_id": reply.thread_id,
        "author_id": reply.author_id,
        "author_name": reply.author.full_name if reply.author else None,
        "body": reply.body,
        "helpful_count": reply.helpful_count,
        "created_at": reply.created_at,
    }


def serialize_thread(thread: DiscussionThread, include_replies: bool = True) -> dict:
    return {
        "id": thread.id,
        "course_id": thread.course_id,
        "author_id": thread.author_id,
        "author_name": thread.author.full_name if thread.author else None,
        "title": thread.title,
        "body": thread.body,
        "tags": thread.tags,
        "is_resolved": thread.is_resolved,
        "created_at": thread.created_at,
        "reply_count": len(thread.replies),
        "replies": [serialize_reply(reply) for reply in thread.replies] if include_replies else [],
    }


def serialize_quiz_question(question: QuizQuestion, include_answers: bool = False) -> dict:
    return {
        "id": question.id,
        "prompt": question.prompt,
        "option_a": question.option_a,
        "option_b": question.option_b,
        "option_c": question.option_c,
        "option_d": question.option_d,
        "points": question.points,
        "explanation": question.explanation if include_answers else None,
        "correct_option": question.correct_option if include_answers else None,
    }


def select_round_questions(db: Session, quiz: Quiz, user: User, round_size: int = QUIZ_ROUND_SIZE) -> list[QuizQuestion]:
    questions = list(quiz.questions)
    if len(questions) <= round_size:
        return questions

    answered_question_ids = set(
        db.scalars(
            select(QuizAnswer.question_id)
            .join(QuizAttempt, QuizAnswer.attempt_id == QuizAttempt.id)
            .where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == user.id)
        ).all()
    )
    unseen_questions = [question for question in questions if question.id not in answered_question_ids]
    pool = unseen_questions if len(unseen_questions) >= round_size else questions
    return random.sample(pool, round_size)


def serialize_quiz(
    quiz: Quiz,
    include_questions: bool = False,
    include_answers: bool = False,
    round_questions: list[QuizQuestion] | None = None,
) -> dict:
    questions = []
    if include_questions:
        selected_questions = round_questions if round_questions is not None else list(quiz.questions)
        questions = [serialize_quiz_question(question, include_answers=include_answers) for question in selected_questions]
    return {
        "id": quiz.id,
        "course_id": quiz.course_id,
        "title": quiz.title,
        "quiz_type": quiz.quiz_type,
        "description": quiz.description,
        "created_at": quiz.created_at,
        "question_count": len(quiz.questions),
        "round_size": min(QUIZ_ROUND_SIZE, len(quiz.questions)),
        "questions": questions,
    }


def quiz_attempt_response(attempt: QuizAttempt, include_answers: bool = False) -> dict:
    percentage = (attempt.score / attempt.total_points * 100) if attempt.total_points else 0
    payload = {
        "id": attempt.id,
        "quiz_id": attempt.quiz_id,
        "quiz_title": attempt.quiz.title,
        "quiz_type": attempt.quiz.quiz_type,
        "course_id": attempt.quiz.course_id,
        "topic_title": attempt.quiz.course.title if attempt.quiz.course else None,
        "topic_code": attempt.quiz.course.code if attempt.quiz.course else None,
        "user_id": attempt.user_id,
        "score": attempt.score,
        "total_points": attempt.total_points,
        "percentage": round(percentage, 2),
        "seconds_spent": attempt.seconds_spent,
        "question_count": len(attempt.answers),
        "completed_at": attempt.completed_at,
    }
    if include_answers:
        payload["answers"] = [
            {
                "question_id": answer.question_id,
                "prompt": answer.question.prompt,
                "selected_option": answer.selected_option,
                "correct_option": answer.question.correct_option,
                "is_correct": answer.is_correct,
                "points_awarded": answer.points_awarded,
                "points": answer.question.points,
                "explanation": answer.question.explanation,
                "options": {
                    "a": answer.question.option_a,
                    "b": answer.question.option_b,
                    "c": answer.question.option_c,
                    "d": answer.question.option_d,
                },
            }
            for answer in attempt.answers
        ]
    return payload


def csv_response(filename: str, headers: list[str], rows: Iterable[Iterable]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def ensure_seed_quiz(db: Session, course: Course, quiz_type: str, title: str, description: str) -> Quiz:
    quiz = db.scalar(
        select(Quiz)
        .where(Quiz.course_id == course.id, Quiz.quiz_type == quiz_type)
        .order_by(Quiz.id)
        .limit(1)
    )
    if quiz is None:
        quiz = Quiz(course_id=course.id, title=title, quiz_type=quiz_type, description=description)
        db.add(quiz)
        db.flush()
    else:
        quiz.title = title
        quiz.description = description
    return quiz


def ensure_seed_questions(db: Session, quiz: Quiz, questions: list[dict]) -> None:
    existing_prompts = {
        prompt
        for prompt in db.scalars(select(QuizQuestion.prompt).where(QuizQuestion.quiz_id == quiz.id)).all()
    }
    for question in questions:
        if question["prompt"] in existing_prompts:
            continue
        db.add(QuizQuestion(quiz_id=quiz.id, **question))


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

        ensure_seed_questions(db, pretest, bank[:QUIZ_ROUND_SIZE]) 
        ensure_seed_questions(db, practice, bank)
        ensure_seed_questions(db, posttest, bank[-QUIZ_ROUND_SIZE:])


def seed_database(db: Session) -> None:
    researcher_email = normalized_email(os.environ.get("SEED_RESEARCHER_EMAIL", "researcher@abuzaria.edu.ng"))
    researcher_password = os.environ.get("SEED_RESEARCHER_PASSWORD", "Research@12345")

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
        topics = [
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
                title="Research Project in Computer Science Education",
                code="SECS403",
                description="Research design, methodology, data collection, analysis, and reporting in CS education research.",
                facilitator="Research Project Supervisor",
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
        db.add_all(topics)
        db.flush()

    courses_by_code = {topic.code: topic for topic in db.scalars(select(Course)).all()}

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
    if not engine.url.drivername.startswith("sqlite"):
        return

    with engine.connect() as connection:
        inspector = inspect(connection)
        table_names = inspector.get_table_names()
        if "courses" in table_names:
            return

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table_name in table_names:
            safe_name = table_name.replace('"', '""')
            connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{safe_name}"')
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_stale_sqlite_schema()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(
    title="ABU Zaria Community of Practice Research Platform",
    version="2.0.0",
    description="A FastAPI edTech platform for learning engagement, academic performance, and community of practice research.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def app_home():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "ABU Zaria Community of Practice Research Platform", "docs": "/docs"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "cop-research-platform"}


@app.post("/api/auth/register")
def register(payload: UserCreate, db: SessionDep):
    if not payload.accepted_research_consent:
        raise HTTPException(status_code=400, detail="Research consent is required before registration.")

    user = User(
        research_id=generate_research_id(db),
        full_name=payload.full_name.strip(),
        email=normalized_email(payload.email),
        password_hash=hash_password(payload.password),
        role="student",
        study_group=payload.study_group,
        programme=payload.programme,
        department=payload.department,
        level=payload.level,
        interests=payload.interests,
    )
    db.add(user)
    try:
        db.flush()
        db.add(ConsentRecord(user_id=user.id, agreed=True, consent_version="v1"))
        log_activity(db, user, "registered", "user", user.id, {"study_group": user.study_group})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc

    db.refresh(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": serialize_user(user)}


@app.post("/api/auth/login")
def login(payload: UserLogin, db: SessionDep):
    user = db.scalar(select(User).where(User.email == normalized_email(payload.email)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user.last_login_at = datetime.utcnow()
    log_activity(db, user, "logged_in", "user", user.id)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": serialize_user(user)}


@app.get("/api/me")
def me(current_user: CurrentUser):
    return serialize_user(current_user)


@app.post("/api/consent")
def record_consent(payload: ConsentCreate, db: SessionDep, current_user: CurrentUser):
    consent = ConsentRecord(
        user_id=current_user.id,
        consent_version=payload.consent_version,
        agreed=payload.agreed,
        notes=payload.notes,
    )
    db.add(consent)
    log_activity(db, current_user, "consent_recorded", "consent", None, {"agreed": payload.agreed})
    db.commit()
    db.refresh(consent)
    return {"id": consent.id, "agreed": consent.agreed, "consent_version": consent.consent_version}


@app.get("/api/topics")
def list_topics(db: SessionDep):
    topics = db.scalars(select(Topic).order_by(Topic.title)).all()
    return [serialize_course(topic) for topic in topics]


@app.post("/api/topics")
def create_topic(payload: TopicCreate, db: SessionDep, current_user: ContentManagerUser):
    topic = Topic(
        title=payload.title.strip(),
        code=payload.code.strip().upper(),
        description=payload.description,
        facilitator=payload.facilitator,
    )
    db.add(topic)
    try:
        db.flush()
        log_activity(db, current_user, "topic_created", "topic", topic.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A topic with this title or code already exists.") from exc
    db.refresh(topic)
    return serialize_course(topic)


@app.post("/api/topics/{course_id}/join")
def join_topic(course_id: int, payload: MembershipCreate, db: SessionDep, current_user: CurrentUser):
    topic = db.get(Topic, course_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found.")

    existing = db.scalar(
        select(Membership).where(Membership.course_id == course_id, Membership.user_id == current_user.id)
    )
    if existing:
        return {"message": "Already joined this topic.", "topic": serialize_course(topic)}

    membership = Membership(user_id=current_user.id, course_id=course_id, learning_goal=payload.learning_goal)
    db.add(membership)
    log_activity(db, current_user, "topic_joined", "topic", course_id, {"learning_goal": payload.learning_goal})
    db.commit()
    db.refresh(topic)
    return {"message": "Topic joined.", "topic": serialize_course(topic)}


@app.get("/api/resources")
def list_resources(db: SessionDep, course_id: int | None = Query(default=None)):
    query = select(Resource).order_by(Resource.created_at.desc())
    if course_id is not None:
        query = query.where(Resource.course_id == course_id)
    resources = db.scalars(query).all()
    return [serialize_resource(resource) for resource in resources]


@app.post("/api/resources")
def create_resource(payload: ResourceCreate, db: SessionDep, current_user: ContentManagerUser):
    topic = db.get(Topic, payload.course_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found.")

    resource = Resource(
        course_id=payload.course_id,
        created_by_id=current_user.id,
        title=payload.title,
        resource_type=payload.resource_type,
        difficulty=payload.difficulty,
        estimated_minutes=payload.estimated_minutes,
        url=payload.url,
        body=payload.body,
    )
    db.add(resource)
    db.flush()
    log_activity(db, current_user, "resource_created", "resource", resource.id, {"course_id": payload.course_id})
    db.commit()
    db.refresh(resource)
    return serialize_resource(resource)


@app.get("/api/resources/{resource_id}")
def get_resource(
    resource_id: int,
    db: SessionDep,
    current_user: CurrentUser,
    seconds_spent: int = Query(default=0, ge=0),
):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")

    view = ResourceView(resource_id=resource.id, user_id=current_user.id, seconds_spent=seconds_spent)
    db.add(view)
    log_activity(
        db,
        current_user,
        "resource_viewed",
        "resource",
        resource.id,
        {"course_id": resource.course_id, "seconds_spent": seconds_spent},
    )
    db.commit()
    db.refresh(resource)
    return serialize_resource(resource)


@app.post("/api/resources/{resource_id}/feedback")
def submit_resource_feedback(
    resource_id: int,
    payload: ResourceFeedbackCreate,
    db: SessionDep,
    current_user: CurrentUser,
):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found.")

    feedback = ResourceFeedback(
        resource_id=resource_id,
        user_id=current_user.id,
        usefulness_rating=payload.usefulness_rating,
        clarity_rating=payload.clarity_rating,
        confidence_after=payload.confidence_after,
        comment=payload.comment,
    )
    db.add(feedback)
    log_activity(
        db,
        current_user,
        "resource_feedback_submitted",
        "resource",
        resource_id,
        {"usefulness_rating": payload.usefulness_rating, "clarity_rating": payload.clarity_rating},
    )
    db.commit()
    db.refresh(feedback)
    return {"message": "Feedback recorded.", "id": feedback.id}


@app.get("/api/discussions")
def list_discussions(
    db: SessionDep,
    course_id: int | None = Query(default=None),
    include_replies: bool = Query(default=True),
):
    query = select(DiscussionThread).order_by(DiscussionThread.created_at.desc())
    if course_id is not None:
        query = query.where(DiscussionThread.course_id == course_id)
    threads = db.scalars(query).all()
    return [serialize_thread(thread, include_replies=include_replies) for thread in threads]


@app.post("/api/discussions")
def create_discussion(payload: DiscussionThreadCreate, db: SessionDep, current_user: CurrentUser):
    topic = db.get(Topic, payload.course_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found.")

    thread = DiscussionThread(
        course_id=payload.course_id,
        author_id=current_user.id,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
    )
    db.add(thread)
    db.flush()
    log_activity(db, current_user, "discussion_created", "discussion", thread.id, {"course_id": payload.course_id})
    db.commit()
    db.refresh(thread)
    return serialize_thread(thread)


@app.post("/api/discussions/{thread_id}/replies")
def create_reply(
    thread_id: int,
    payload: DiscussionReplyCreate,
    db: SessionDep,
    current_user: CurrentUser,
):
    thread = db.get(DiscussionThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Discussion not found.")

    reply = DiscussionReply(thread_id=thread_id, author_id=current_user.id, body=payload.body)
    thread.updated_at = datetime.utcnow()
    db.add(reply)
    db.flush()
    log_activity(db, current_user, "discussion_reply_created", "reply", reply.id, {"thread_id": thread_id})
    db.commit()
    db.refresh(reply)
    return serialize_reply(reply)


@app.post("/api/discussions/{thread_id}/resolve")
def resolve_discussion(thread_id: int, db: SessionDep, current_user: CurrentUser):
    thread = db.get(DiscussionThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Discussion not found.")
    if thread.author_id != current_user.id and current_user.role not in CONTENT_ROLES:
        raise HTTPException(status_code=403, detail="Only the author or a facilitator can resolve this discussion.")

    thread.is_resolved = True
    thread.updated_at = datetime.utcnow()
    log_activity(db, current_user, "discussion_resolved", "discussion", thread_id)
    db.commit()
    db.refresh(thread)
    return serialize_thread(thread)


@app.post("/api/replies/{reply_id}/helpful")
def mark_reply_helpful(reply_id: int, db: SessionDep, current_user: CurrentUser):
    reply = db.get(DiscussionReply, reply_id)
    if reply is None:
        raise HTTPException(status_code=404, detail="Reply not found.")

    existing = db.scalar(
        select(ReplyHelpfulVote).where(ReplyHelpfulVote.reply_id == reply_id, ReplyHelpfulVote.user_id == current_user.id)
    )
    if existing:
        return {"message": "Reply already marked as helpful.", "reply": serialize_reply(reply)}

    db.add(ReplyHelpfulVote(reply_id=reply_id, user_id=current_user.id))
    reply.helpful_count += 1
    log_activity(db, current_user, "reply_marked_helpful", "reply", reply_id)
    db.commit()
    db.refresh(reply)
    return {"message": "Marked as helpful.", "reply": serialize_reply(reply)}


@app.get("/api/quizzes")
def list_quizzes(
    db: SessionDep,
    course_id: int | None = Query(default=None),
    quiz_type: str | None = Query(default=None),
):
    query = select(Quiz).order_by(Quiz.created_at.desc())
    if course_id is not None:
        query = query.where(Quiz.course_id == course_id)
    if quiz_type is not None:
        query = query.where(Quiz.quiz_type == quiz_type)
    quizzes = db.scalars(query).all()
    return [serialize_quiz(quiz) for quiz in quizzes]


@app.post("/api/quizzes")
def create_quiz(payload: QuizCreate, db: SessionDep, current_user: ContentManagerUser):
    topic = db.get(Topic, payload.course_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found.")
    quiz = Quiz(
        course_id=payload.course_id,
        title=payload.title,
        quiz_type=payload.quiz_type,
        description=payload.description,
    )
    db.add(quiz)
    db.flush()
    log_activity(db, current_user, "quiz_created", "quiz", quiz.id, {"quiz_type": payload.quiz_type})
    db.commit()
    db.refresh(quiz)
    return serialize_quiz(quiz)


@app.post("/api/quizzes/{quiz_id}/questions")
def create_quiz_question(
    quiz_id: int,
    payload: QuizQuestionCreate,
    db: SessionDep,
    current_user: ContentManagerUser,
):
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    question = QuizQuestion(
        quiz_id=quiz_id,
        prompt=payload.prompt,
        option_a=payload.option_a,
        option_b=payload.option_b,
        option_c=payload.option_c,
        option_d=payload.option_d,
        correct_option=payload.correct_option,
        explanation=payload.explanation,
        points=payload.points,
    )
    db.add(question)
    db.flush()
    log_activity(db, current_user, "quiz_question_created", "quiz_question", question.id, {"quiz_id": quiz_id})
    db.commit()
    db.refresh(quiz)
    return serialize_quiz(quiz, include_questions=True, include_answers=True)


@app.get("/api/quizzes/{quiz_id}")
def get_quiz(quiz_id: int, db: SessionDep, current_user: CurrentUser):
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    include_answers = current_user.role in CONTENT_ROLES
    log_activity(db, current_user, "quiz_viewed", "quiz", quiz_id, {"quiz_type": quiz.quiz_type})
    db.commit()
    return serialize_quiz(quiz, include_questions=True, include_answers=include_answers)


@app.post("/api/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: int, payload: QuizSubmit, db: SessionDep, current_user: CurrentUser):
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")
    if not quiz.questions:
        raise HTTPException(status_code=400, detail="This quiz has no questions yet.")

    answer_map = {answer.question_id: answer.selected_option for answer in payload.answers}
    total_points = float(sum(question.points for question in quiz.questions))
    score = 0.0

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        user_id=current_user.id,
        score=0,
        total_points=total_points,
        seconds_spent=payload.seconds_spent,
        completed_at=datetime.utcnow(),
    )
    db.add(attempt)
    db.flush()

    for question in quiz.questions:
        selected = answer_map.get(question.id)
        is_correct = selected == question.correct_option
        points_awarded = float(question.points if is_correct else 0)
        score += points_awarded
        db.add(
            QuizAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option=selected,
                is_correct=is_correct,
                points_awarded=points_awarded,
            )
        )

    attempt.score = score
    log_activity(
        db,
        current_user,
        "quiz_submitted",
        "quiz",
        quiz_id,
        {"quiz_type": quiz.quiz_type, "score": score, "total_points": total_points},
    )
    db.commit()
    db.refresh(attempt)
    return quiz_attempt_response(attempt, include_answers=True)


@app.get("/api/quiz-attempts")
def list_quiz_attempts(db: SessionDep, current_user: CurrentUser):
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.completed_at.desc())
    ).all()
    return [quiz_attempt_response(attempt) for attempt in attempts]


@app.get("/api/quiz-attempts/{attempt_id}")
def get_quiz_attempt(attempt_id: int, db: SessionDep, current_user: CurrentUser):
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    if attempt.user_id != current_user.id and current_user.role not in RESEARCH_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view this attempt.")
    return quiz_attempt_response(attempt, include_answers=True)


@app.post("/api/reflections")
def create_reflection(payload: ReflectionCreate, db: SessionDep, current_user: CurrentUser):
    reflection = Reflection(
        user_id=current_user.id,
        week_label=payload.week_label,
        learned=payload.learned,
        challenge=payload.challenge,
        community_help=payload.community_help,
        confidence_rating=payload.confidence_rating,
        engagement_rating=payload.engagement_rating,
        suggestions=payload.suggestions,
    )
    db.add(reflection)
    db.flush()
    log_activity(
        db,
        current_user,
        "reflection_submitted",
        "reflection",
        reflection.id,
        {"confidence_rating": payload.confidence_rating, "engagement_rating": payload.engagement_rating},
    )
    db.commit()
    db.refresh(reflection)
    return reflection


@app.post("/api/feedback")
def create_platform_feedback(payload: PlatformFeedbackCreate, db: SessionDep, current_user: CurrentUser):
    feedback = PlatformFeedback(
        user_id=current_user.id,
        category=payload.category,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    db.flush()
    log_activity(
        db,
        current_user,
        "platform_feedback_submitted",
        "platform_feedback",
        feedback.id,
        {"category": payload.category, "rating": payload.rating},
    )
    db.commit()
    db.refresh(feedback)
    return {"message": "Platform feedback recorded.", "id": feedback.id}


@app.post("/api/activity")
def create_activity(payload: ActivityCreate, db: SessionDep, current_user: CurrentUser):
    event = log_activity(
        db,
        current_user,
        payload.action,
        payload.entity_type,
        payload.entity_id,
        payload.metadata,
    )
    db.commit()
    db.refresh(event)
    return {"message": "Activity recorded.", "id": event.id}


@app.post("/api/academic-records")
def create_academic_record(payload: AcademicRecordCreate, db: SessionDep, current_user: ResearcherUser):
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    record = AcademicRecord(
        user_id=payload.user_id,
        assessment_name=payload.assessment_name,
        assessment_type=payload.assessment_type,
        score=payload.score,
        total=payload.total,
        notes=payload.notes,
    )
    db.add(record)
    db.flush()
    log_activity(
        db,
        current_user,
        "academic_record_created",
        "academic_record",
        record.id,
        {"student_research_id": user.research_id, "assessment_type": payload.assessment_type},
    )
    db.commit()
    db.refresh(record)
    return {"message": "Academic record saved.", "id": record.id}


@app.get("/api/research/users")
def research_users(db: SessionDep, current_user: ResearcherUser):
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [serialize_user(user) for user in users]


@app.get("/api/research/dashboard")
def research_dashboard(db: SessionDep, current_user: ResearcherUser):
    users = db.scalar(select(func.count(User.id))) or 0
    experimental_users = db.scalar(select(func.count(User.id)).where(User.study_group == "experimental")) or 0
    control_users = db.scalar(select(func.count(User.id)).where(User.study_group == "control")) or 0
    quiz_average = db.scalar(
        select(func.avg((QuizAttempt.score * 100.0) / QuizAttempt.total_points)).where(QuizAttempt.total_points > 0)
    )
    engagement_average = db.scalar(select(func.avg(Reflection.engagement_rating)))

    return {
        "users": users,
        "experimental_users": experimental_users,
        "control_users": control_users,
        "topics": db.scalar(select(func.count(Topic.id))) or 0,
        "resources": db.scalar(select(func.count(Resource.id))) or 0,
        "discussions": db.scalar(select(func.count(DiscussionThread.id))) or 0,
        "replies": db.scalar(select(func.count(DiscussionReply.id))) or 0,
        "quiz_attempts": db.scalar(select(func.count(QuizAttempt.id))) or 0,
        "reflections": db.scalar(select(func.count(Reflection.id))) or 0,
        "feedback_items": (db.scalar(select(func.count(PlatformFeedback.id))) or 0)
        + (db.scalar(select(func.count(ResourceFeedback.id))) or 0),
        "average_quiz_percentage": round(float(quiz_average or 0), 2),
        "average_engagement_rating": round(float(engagement_average or 0), 2),
        "activity_events": db.scalar(select(func.count(ActivityLog.id))) or 0,
    }


def export_users(db: Session) -> tuple[list[str], list[list]]:
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return (
        ["research_id", "study_group", "role", "programme", "department", "level", "interests", "created_at"],
        [
            [
                user.research_id,
                user.study_group,
                user.role,
                user.programme,
                user.department,
                user.level,
                user.interests,
                user.created_at,
            ]
            for user in users
        ],
    )


def export_activity(db: Session) -> tuple[list[str], list[list]]:
    logs = db.scalars(select(ActivityLog).order_by(ActivityLog.created_at)).all()
    return (
        ["event_id", "research_id", "action", "entity_type", "entity_id", "metadata", "created_at"],
        [
            [
                log.id,
                log.user.research_id if log.user else None,
                log.action,
                log.entity_type,
                log.entity_id,
                log.metadata_json,
                log.created_at,
            ]
            for log in logs
        ],
    )


def export_quiz_attempts(db: Session) -> tuple[list[str], list[list]]:
    attempts = db.scalars(select(QuizAttempt).order_by(QuizAttempt.completed_at)).all()
    return (
        [
            "attempt_id",
            "research_id",
            "study_group",
            "topic_code",
            "quiz_title",
            "quiz_type",
            "score",
            "total_points",
            "percentage",
            "seconds_spent",
            "completed_at",
        ],
        [
            [
                attempt.id,
                attempt.user.research_id,
                attempt.user.study_group,
                attempt.quiz.course.code,
                attempt.quiz.title,
                attempt.quiz.quiz_type,
                attempt.score,
                attempt.total_points,
                round((attempt.score / attempt.total_points * 100) if attempt.total_points else 0, 2),
                attempt.seconds_spent,
                attempt.completed_at,
            ]
            for attempt in attempts
        ],
    )


def export_feedback(db: Session) -> tuple[list[str], list[list]]:
    rows = []
    for feedback in db.scalars(select(ResourceFeedback).order_by(ResourceFeedback.created_at)).all():
        rows.append(
            [
                "resource",
                feedback.id,
                feedback.user.research_id,
                feedback.resource.title,
                feedback.usefulness_rating,
                feedback.clarity_rating,
                feedback.confidence_after,
                feedback.comment,
                feedback.created_at,
            ]
        )
    for feedback in db.scalars(select(PlatformFeedback).order_by(PlatformFeedback.created_at)).all():
        rows.append(
            [
                "platform",
                feedback.id,
                feedback.user.research_id,
                feedback.category,
                feedback.rating,
                None,
                None,
                feedback.comment,
                feedback.created_at,
            ]
        )
    return (
        [
            "feedback_type",
            "feedback_id",
            "research_id",
            "target_or_category",
            "rating_or_usefulness",
            "clarity_rating",
            "confidence_after",
            "comment",
            "created_at",
        ],
        rows,
    )


def export_reflections(db: Session) -> tuple[list[str], list[list]]:
    reflections = db.scalars(select(Reflection).order_by(Reflection.created_at)).all()
    return (
        [
            "reflection_id",
            "research_id",
            "study_group",
            "week_label",
            "confidence_rating",
            "engagement_rating",
            "learned",
            "challenge",
            "community_help",
            "suggestions",
            "created_at",
        ],
        [
            [
                reflection.id,
                reflection.user.research_id,
                reflection.user.study_group,
                reflection.week_label,
                reflection.confidence_rating,
                reflection.engagement_rating,
                reflection.learned,
                reflection.challenge,
                reflection.community_help,
                reflection.suggestions,
                reflection.created_at,
            ]
            for reflection in reflections
        ],
    )


def export_discussions(db: Session) -> tuple[list[str], list[list]]:
    rows = []
    for thread in db.scalars(select(DiscussionThread).order_by(DiscussionThread.created_at)).all():
        rows.append(
            [
                "thread",
                thread.id,
                thread.author.research_id,
                thread.topic.code,
                thread.title,
                thread.body,
                thread.tags,
                thread.is_resolved,
                len(thread.replies),
                thread.created_at,
            ]
        )
    for reply in db.scalars(select(DiscussionReply).order_by(DiscussionReply.created_at)).all():
        rows.append(
            [
                "reply",
                reply.id,
                reply.author.research_id,
                reply.thread.topic.code,
                reply.thread.title,
                reply.body,
                None,
                None,
                reply.helpful_count,
                reply.created_at,
            ]
        )
    return (
        [
            "item_type",
            "item_id",
            "research_id",
            "topic_code",
            "thread_title",
            "text",
            "tags",
            "is_resolved",
            "reply_or_helpful_count",
            "created_at",
        ],
        rows,
    )


def export_academic_records(db: Session) -> tuple[list[str], list[list]]:
    records = db.scalars(select(AcademicRecord).order_by(AcademicRecord.recorded_at)).all()
    return (
        [
            "record_id",
            "research_id",
            "study_group",
            "assessment_name",
            "assessment_type",
            "score",
            "total",
            "percentage",
            "notes",
            "recorded_at",
        ],
        [
            [
                record.id,
                record.user.research_id,
                record.user.study_group,
                record.assessment_name,
                record.assessment_type,
                record.score,
                record.total,
                round((record.score / record.total * 100) if record.total else 0, 2),
                record.notes,
                record.recorded_at,
            ]
            for record in records
        ],
    )


def export_combined(db: Session) -> tuple[list[str], list[list]]:
    rows = []
    users = db.scalars(select(User).order_by(User.research_id)).all()
    for user in users:
        attempts = user.quiz_attempts
        pretest_scores = [
            (attempt.score / attempt.total_points * 100)
            for attempt in attempts
            if attempt.total_points and attempt.quiz.quiz_type == "pretest"
        ]
        posttest_scores = [
            (attempt.score / attempt.total_points * 100)
            for attempt in attempts
            if attempt.total_points and attempt.quiz.quiz_type == "posttest"
        ]
        practice_scores = [
            (attempt.score / attempt.total_points * 100)
            for attempt in attempts
            if attempt.total_points and attempt.quiz.quiz_type == "practice"
        ]
        logs = user.activity_logs
        reflections = user.reflections
        academic = user.academic_records
        rows.append(
            [
                user.research_id,
                user.study_group,
                user.level,
                len(logs),
                len(user.memberships),
                len(user.resource_views),
                len(user.threads),
                len(user.replies),
                len(attempts),
                round(sum(pretest_scores) / len(pretest_scores), 2) if pretest_scores else None,
                round(sum(practice_scores) / len(practice_scores), 2) if practice_scores else None,
                round(sum(posttest_scores) / len(posttest_scores), 2) if posttest_scores else None,
                round(sum(r.engagement_rating for r in reflections) / len(reflections), 2) if reflections else None,
                round(sum(r.confidence_rating for r in reflections) / len(reflections), 2) if reflections else None,
                round(
                    sum(record.score / record.total * 100 for record in academic if record.total)
                    / len([record for record in academic if record.total]),
                    2,
                )
                if academic
                else None,
            ]
        )
    return (
        [
            "research_id",
            "study_group",
            "level",
            "activity_event_count",
            "topic_memberships",
            "resource_views",
            "discussion_threads",
            "discussion_replies",
            "quiz_attempts",
            "pretest_avg_percent",
            "practice_avg_percent",
            "posttest_avg_percent",
            "reflection_engagement_avg",
            "reflection_confidence_avg",
            "external_academic_avg_percent",
        ],
        rows,
    )


EXPORTERS = {
    "users": export_users,
    "activity": export_activity,
    "quiz_attempts": export_quiz_attempts,
    "feedback": export_feedback,
    "reflections": export_reflections,
    "discussions": export_discussions,
    "academic_records": export_academic_records,
    "combined": export_combined,
}


@app.get("/api/research/export/{dataset}")
def export_dataset(dataset: str, db: SessionDep, current_user: ResearcherUser):
    exporter = EXPORTERS.get(dataset)
    if exporter is None:
        available = ", ".join(sorted(EXPORTERS))
        raise HTTPException(status_code=404, detail=f"Unknown dataset. Available datasets: {available}.")
    headers, rows = exporter(db)
    return csv_response(f"{dataset}.csv", headers, rows)
