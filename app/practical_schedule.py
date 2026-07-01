from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import engine
from model import Course, PracticalExercise


LAGOS_TZ = ZoneInfo("Africa/Lagos")
PRACTICAL_RELEASE_HOURS = (8, 12, 19)
PRACTICAL_SOURCE = "local-daily-bank"


@dataclass(frozen=True)
class PracticalRelease:
    key: str
    release_at_local: datetime
    release_at_utc: datetime
    expires_at_local: datetime
    expires_at_utc: datetime


def current_practical_release(now: datetime | None = None) -> PracticalRelease:
    if now is None:
        now_local = datetime.now(LAGOS_TZ)
    elif now.tzinfo is None:
        now_local = now.replace(tzinfo=timezone.utc).astimezone(LAGOS_TZ)
    else:
        now_local = now.astimezone(LAGOS_TZ)

    today = now_local.date()
    today_8 = datetime(today.year, today.month, today.day, 8, tzinfo=LAGOS_TZ)
    today_12 = datetime(today.year, today.month, today.day, 12, tzinfo=LAGOS_TZ)
    today_19 = datetime(today.year, today.month, today.day, 19, tzinfo=LAGOS_TZ)

    WINDOW_DURATION = timedelta(hours=2)

    if now_local >= today_19:
        release_at = today_19
        expires_at = today_19 + WINDOW_DURATION
    elif now_local >= today_12:
        release_at = today_12
        expires_at = today_12 + WINDOW_DURATION
    elif now_local >= today_8:
        release_at = today_8
        expires_at = today_8 + WINDOW_DURATION
    else:
        yesterday = today - timedelta(days=1)
        release_at = datetime(yesterday.year, yesterday.month, yesterday.day, 19, tzinfo=LAGOS_TZ)
        expires_at = release_at + WINDOW_DURATION

    return PracticalRelease(
        key=f"{release_at:%Y-%m-%d}-{release_at.hour:02d}",
        release_at_local=release_at,
        release_at_utc=_utc_naive(release_at),
        expires_at_local=expires_at,
        expires_at_utc=_utc_naive(expires_at),
    )


def ensure_practical_release_schema() -> None:
    with engine.begin() as connection:
        inspector = sa_inspect(connection)
        if "practical_exercises" not in inspector.get_table_names():
            return

        columns = {column["name"] for column in inspector.get_columns("practical_exercises")}
        additions = {
            "release_key": "ALTER TABLE practical_exercises ADD COLUMN release_key VARCHAR(40)",
            "release_at": "ALTER TABLE practical_exercises ADD COLUMN release_at TIMESTAMP",
            "expires_at": "ALTER TABLE practical_exercises ADD COLUMN expires_at TIMESTAMP",
            "source": "ALTER TABLE practical_exercises ADD COLUMN source VARCHAR(80)",
        }
        for column, statement in additions.items():
            if column not in columns:
                connection.exec_driver_sql(statement)

        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_practical_exercises_release_key "
            "ON practical_exercises (release_key)"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_practical_exercises_release_unique "
            "ON practical_exercises (course_id, release_key, practical_type, title)"
        )


def ensure_daily_practicals(
    db: Session,
    course_ids: list[int] | set[int] | tuple[int, ...],
    now: datetime | None = None,
) -> PracticalRelease:
    release = current_practical_release(now)
    scoped_course_ids = [int(course_id) for course_id in course_ids if course_id is not None]
    if not scoped_course_ids:
        return release

    courses = db.scalars(
        select(Course).where(Course.id.in_(scoped_course_ids)).order_by(Course.code)
    ).all()
    if not courses:
        return release

    existing_titles = set(
        db.execute(
            select(PracticalExercise.course_id, PracticalExercise.title).where(
                PracticalExercise.course_id.in_([course.id for course in courses]),
                PracticalExercise.release_key == release.key,
            )
        ).all()
    )

    created = False
    for course in courses:
        for spec in build_daily_practical_specs(course, release):
            if (course.id, spec["title"]) in existing_titles:
                continue
            db.add(
                PracticalExercise(
                    course_id=course.id,
                    title=spec["title"],
                    practical_type=spec["practical_type"],
                    difficulty=spec["difficulty"],
                    prompt=spec["prompt"],
                    starter_code=spec["starter_code"],
                    expected_output=spec["expected_output"],
                    solution_notes=spec["solution_notes"],
                    checks_json=json.dumps(spec["checks"]),
                    release_key=release.key,
                    release_at=release.release_at_utc,
                    expires_at=release.expires_at_utc,
                    source=PRACTICAL_SOURCE,
                )
            )
            created = True

    if created:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

    return release


def _select_builders(builders: list, seed: int, count: int) -> list:
    shuffled = sorted(builders, key=lambda b: _stable_int(seed, b.__name__))
    return shuffled[:count]


def build_daily_practical_specs(course: Course, release: PracticalRelease) -> list[dict]:
    PYTHON_BUILDERS = [
        _python_count_scores, _python_average_minutes, _python_format_course,
        _python_topic_counts, _python_linear_search, _python_top_scores,
        _python_palindrome, _python_reverse_string, _python_two_sum,
        _python_fizzbuzz, _python_count_vowels, _python_even_numbers,
        _python_second_largest, _python_factorial, _python_unique_elements,
        _python_positive_count, _python_anagram_check, _python_max_in_list,
        _python_merge_sorted, _python_count_words,
    ]
    JAVA_BUILDERS = [
        _java_count_scores, _java_average_scores, _java_format_course,
        _java_find_index, _java_highest_value, _java_contains_topic,
        _java_palindrome, _java_reverse_string, _java_two_sum,
        _java_fizzbuzz, _java_count_vowels, _java_even_numbers,
        _java_second_largest, _java_factorial, _java_positive_count,
        _java_anagram_check, _java_max_in_array, _java_merge_sorted,
        _java_count_words, _java_fibonacci,
        _java_print_triangle, _java_email_parser, _java_password_gen,
        _java_box_surface, _java_bank_account, _java_student_average,
        _java_quadratic_roots, _java_arithmetic_progression, _java_grade_stats,
        _java_investment_future,
        _java_employee_deductions, _java_author_tostring, _java_vector_product,
        _java_profit_stats, _java_matrix_add, _java_magic_square,
        _java_recursive_factorial, _java_recursive_fibonacci,
        _java_weighed_item, _java_rental_mileage, _java_total_payroll,
    ]
    DB_BUILDERS = [
        _sql_select_scores, _sql_group_enrolments, _sql_join_attempts,
        _sql_create_score_table, _sql_update_bonus, _sql_having_average,
        _sql_create_index, _sql_left_join, _sql_subquery_avg,
        _sql_rank_window, _sql_case_label, _sql_coalesce_default,
        _sql_delete_old, _sql_insert_select, _sql_like_search,
        _sql_count_distinct, _sql_union_results, _sql_exists_check,
        _sql_date_group, _sql_alter_add,
    ]
    py_seed = _stable_int(course.code, release.key, "python")
    java_seed = _stable_int(course.code, release.key, "java")
    db_seed = _stable_int(course.code, release.key, "database")

    python_builders = _select_builders(PYTHON_BUILDERS, py_seed, 1)
    java_builders = _select_builders(JAVA_BUILDERS, java_seed, 1)
    db_builders = _select_builders(DB_BUILDERS, db_seed, 3)

    specs = [
        python_builders[0](course, py_seed),
        java_builders[0](course, java_seed),
        db_builders[0](course, db_seed),
        db_builders[1](course, db_seed + 37),
        db_builders[2](course, db_seed + 73),
    ]

    return specs


def _python_count_scores(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    threshold = _choice([45, 50, 55, 60, 65, 70, 75], seed)
    fn = f"count_at_least_{suffix}"
    return _spec(
        title=f"Python: Count Scores At Least {threshold}",
        practical_type="python",
        difficulty=_difficulty(seed),
        prompt=(
            f"Write a Python function named {fn}(scores) for {course.code}. "
            f"It should return how many numeric scores are greater than or equal to {threshold}."
        ),
        starter_code=f"def {fn}(scores):\n    # count scores greater than or equal to {threshold}\n    pass",
        expected_output=f"{fn}([42, {threshold}, {threshold + 8}]) returns 2.",
        solution_notes="Loop through the list, count values that meet the threshold, and return the count.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses the score threshold", "contains_any": [f">= {threshold}", f">={threshold}"]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([42, {threshold}, {threshold + 8}]))", "expected_output": "2"},
        ],
    )


def _python_average_minutes(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"average_minutes_{suffix}"
    sample = _choice([12, 15, 18, 20, 25, 30], seed)
    return _spec(
        title="Python: Average Study Minutes",
        practical_type="python",
        difficulty=_difficulty(seed),
        prompt=(
            f"Write {fn}(minutes) to return the average number of study minutes for {course.title}. "
            "Return 0 when the list is empty."
        ),
        starter_code=f"def {fn}(minutes):\n    # return the average, or 0 for an empty list\n    pass",
        expected_output=f"{fn}([{sample}, {sample + 5}, {sample + 10}]) returns {sample + 5}.",
        solution_notes="Guard against an empty list, then divide sum(minutes) by len(minutes).",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Handles empty lists", "contains_all": ["0"]},
            {"label": "Calculates an average", "contains_all": ["sum", "len"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([{sample}, {sample + 5}, {sample + 10}]))", "expected_output": str(sample + 5)},
        ],
    )


def _python_format_course(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"format_course_{suffix}"
    return _spec(
        title="Python: Format Course Label",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(code, title) to return a label in the format 'CODE - Title'. "
            "The course code should be uppercase."
        ),
        starter_code=f"def {fn}(code, title):\n    # return CODE - Title\n    pass",
        expected_output=f"{fn}('{course.code.lower()}', '{course.title}') returns '{course.code} - {course.title}'.",
        solution_notes="Use code.upper() and string formatting to build the label.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uppercases the code", "contains_all": [".upper("]},
            {"label": "Returns a label", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('{course.code.lower()}', '{course.title}'))", "expected_output": f"'{course.code} - {course.title}'"},
        ],
    )


def _python_topic_counts(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"topic_counts_{suffix}"
    return _spec(
        title="Python: Count Topic Frequency",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(topics) to return a dictionary showing how many times each "
            f"{course.code} topic appears in the list."
        ),
        starter_code=f"def {fn}(topics):\n    counts = {{}}\n    # fill and return counts\n    pass",
        expected_output=f"{fn}(['SQL', 'SQL', 'Python']) returns a dictionary where SQL has count 2.",
        solution_notes="Create a dictionary, loop over topics, and increment the stored count for each topic.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a dictionary", "contains_any": ["{}", "dict("]},
            {"label": "Loops and returns counts", "contains_all": ["for ", "return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(['SQL', 'SQL', 'Python']))", "expected_output": str({'SQL': 2, 'Python': 1}).replace(' ', '')},
        ],
    )


def _python_linear_search(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"find_student_{suffix}"
    return _spec(
        title="Python: Find Student Index",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(students, target) to return the index of target in the students list. "
            "Return -1 when the target name is not present."
        ),
        starter_code=f"def {fn}(students, target):\n    # return the matching index or -1\n    pass",
        expected_output=f"{fn}(['Amina', 'Bala', 'Chidi'], 'Bala') returns 1.",
        solution_notes="Loop with indexes using range(len(students)) or enumerate.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Searches with a loop", "contains_any": ["for ", "while "]},
            {"label": "Handles missing values", "contains_all": ["-1"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(['Amina', 'Bala', 'Chidi'], 'Bala'))", "expected_output": "1"},
        ],
    )


def _python_top_scores(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    limit = _choice([2, 3, 4, 5], seed)
    fn = f"top_scores_{suffix}"
    return _spec(
        title=f"Python: Top {limit} Scores",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(scores) to return the top {limit} scores in descending order. "
            "Do not change the original list."
        ),
        starter_code=f"def {fn}(scores):\n    # return the top {limit} values, highest first\n    pass",
        expected_output=f"{fn}([55, 90, 72, 88]) returns the highest {limit} scores in order.",
        solution_notes="Use sorted(scores, reverse=True) and slice the first required values.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Sorts descending", "contains_any": ["sorted", ".sort("]},
            {"label": "Returns the selected scores", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([55, 90, 72, 88]))", "expected_output": str(sorted([90, 88, 72, 55], reverse=True)[:limit]).replace(' ', '')},
        ],
    )


def _python_palindrome(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"is_palindrome_{suffix}"
    return _spec(
        title="Python: Check Palindrome String",
        practical_type="python",
        difficulty=_difficulty(seed),
        prompt=(
            f"Write a Python function named {fn}(text) for {course.code}. "
            "It should return True when the text reads the same forward and backward, False otherwise. Ignore case."
        ),
        starter_code=f"def {fn}(text):\n    # return True if palindrome, ignoring case\n    pass",
        expected_output=f"{fn}('Racecar') returns True.",
        solution_notes="Convert to lowercase and compare string with its reverse using slicing [::-1].",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Ignores case", "contains_all": [".lower("]},
            {"label": "Compares reversed string", "contains_any": ["[::-1]", "reversed("]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('Racecar'))", "expected_output": "True"},
        ],
    )


def _python_reverse_string(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"reverse_string_{suffix}"
    return _spec(
        title="Python: Reverse String",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(text) to return the string in reverse order. "
            f"Do not use [::-1] slicing — use a loop."
        ),
        starter_code=f"def {fn}(text):\n    # build and return the reversed string\n    pass",
        expected_output=f"{fn}('hello') returns 'olleh'.",
        solution_notes="Initialize an empty result, loop through characters and prepend or build backwards.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a loop", "contains_any": ["for ", "while "]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('hello'))", "expected_output": "olleh"},
        ],
    )


def _python_two_sum(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    target = _choice([7, 9, 10, 12, 15, 18], seed)
    fn = f"two_sum_{suffix}"
    return _spec(
        title=f"Python: Two Sum Equals {target}",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(numbers, target) for {course.code}. "
            f"Return the indices of the two numbers that add up to {target}. "
            "You may assume exactly one solution exists."
        ),
        starter_code=f"def {fn}(numbers, target):\n    # return [i, j] where numbers[i] + numbers[j] == target\n    pass",
        expected_output=f"{fn}([2, 7, 11], 9) returns [0, 1].",
        solution_notes="Use a dictionary to store value-to-index mappings while iterating.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a dictionary", "contains_any": ["{}", "dict("]},
            {"label": "Returns indices", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([2, 7, 11], {target}))", "expected_output": str([0, 1])},
        ],
    )


def _python_fizzbuzz(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"fizzbuzz_{suffix}"
    return _spec(
        title="Python: FizzBuzz Sequence",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(n) to return a list from 1 to n. "
            "For multiples of 3, use 'Fizz' instead of the number. "
            "For multiples of 5, use 'Buzz'. For multiples of both, use 'FizzBuzz'."
        ),
        starter_code=f"def {fn}(n):\n    result = []\n    # build the FizzBuzz list\n    return result",
        expected_output=f"{fn}(5) returns [1, 2, 'Fizz', 4, 'Buzz'].",
        solution_notes="Loop from 1 to n and check divisibility by 3 and 5 with the modulo operator.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses modulo operator", "contains_all": ["%"]},
            {"label": "Returns a list", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(5))", "expected_output": str([1, 2, 'Fizz', 4, 'Buzz']).replace(' ', '')},
        ],
    )


def _python_count_vowels(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"count_vowels_{suffix}"
    return _spec(
        title="Python: Count Vowels",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(text) for {course.code}. "
            "Return the number of vowels (a, e, i, o, u) in the given text, ignoring case."
        ),
        starter_code=f"def {fn}(text):\n    # count and return the number of vowels\n    pass",
        expected_output=f"{fn}('OpenED') returns 3.",
        solution_notes="Use a loop and check membership in a string of vowels, using .lower() for case-insensitivity.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Ignores case", "contains_all": [".lower("]},
            {"label": "Counts vowels", "contains_any": ["'a'", "'e'", "'i'", "'o'", "'u'", "aeiou"]},
            {"label": "Returns a count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('OpenED'))", "expected_output": "3"},
        ],
    )


def _python_even_numbers(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"even_numbers_{suffix}"
    return _spec(
        title="Python: Filter Even Numbers",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(numbers) for {course.code}. "
            "Return a new list containing only the even numbers from the input list."
        ),
        starter_code=f"def {fn}(numbers):\n    # filter and return even numbers\n    pass",
        expected_output=f"{fn}([1, 2, 3, 4, 5]) returns [2, 4].",
        solution_notes="Loop through numbers and use the modulo operator to test divisibility by 2.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Checks even numbers", "contains_all": ["%"]},
            {"label": "Returns a list", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([1, 2, 3, 4, 5]))", "expected_output": str([2, 4])},
        ],
    )


def _python_second_largest(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"second_largest_{suffix}"
    return _spec(
        title="Python: Second Largest Number",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(numbers) for {course.code}. "
            "Return the second largest number in the list. Return None when there are fewer than 2 numbers."
        ),
        starter_code=f"def {fn}(numbers):\n    # return the second largest value or None\n    pass",
        expected_output=f"{fn}([10, 20, 30]) returns 20.",
        solution_notes="Track the largest and second largest values in a single pass.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Handles small lists", "contains_all": ["None"]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([10, 20, 30]))", "expected_output": "20"},
        ],
    )


def _python_factorial(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"factorial_{suffix}"
    return _spec(
        title="Python: Calculate Factorial",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(n) for {course.code}. "
            "Return the factorial of n. Return 1 when n is 0. Use a loop, not recursion."
        ),
        starter_code=f"def {fn}(n):\n    # calculate and return n!\n    pass",
        expected_output=f"{fn}(5) returns 120.",
        solution_notes="Use a for loop multiplying from 1 to n, starting result at 1.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a loop", "contains_any": ["for ", "while "]},
            {"label": "Returns the result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(5))", "expected_output": "120"},
        ],
    )


def _python_unique_elements(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"unique_elements_{suffix}"
    return _spec(
        title="Python: Unique Elements in Order",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(items) for {course.code}. "
            "Return a new list with duplicates removed, preserving the original order."
        ),
        starter_code=f"def {fn}(items):\n    # return unique items preserving order\n    pass",
        expected_output=f"{fn}([3, 1, 2, 1, 3]) returns [3, 1, 2].",
        solution_notes="Use a set to track seen items and a list for ordered results.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a set for tracking", "contains_all": ["set("]},
            {"label": "Returns the result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([3, 1, 2, 1, 3]))", "expected_output": str([3, 1, 2]).replace(' ', '')},
        ],
    )


def _python_positive_count(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"positive_count_{suffix}"
    return _spec(
        title="Python: Count Positive Numbers",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(numbers) for {course.code}. "
            "Return how many numbers in the list are greater than zero."
        ),
        starter_code=f"def {fn}(numbers):\n    # count and return numbers > 0\n    pass",
        expected_output=f"{fn}([-5, 0, 3, 8, -1]) returns 2.",
        solution_notes="Loop through numbers, increment a counter when each number is greater than 0.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Compares to zero", "contains_all": ["> 0"]},
            {"label": "Returns a count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([-5, 0, 3, 8, -1]))", "expected_output": "2"},
        ],
    )


def _python_anagram_check(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"is_anagram_{suffix}"
    return _spec(
        title="Python: Anagram Check",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(word1, word2) for {course.code}. "
            "Return True when both words contain the same letters (ignoring case), False otherwise."
        ),
        starter_code=f"def {fn}(word1, word2):\n    # return True if anagrams, ignoring case\n    pass",
        expected_output=f"{fn}('Listen', 'Silent') returns True.",
        solution_notes="Convert both to lowercase and compare sorted characters or use collections.Counter.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Ignores case", "contains_all": [".lower("]},
            {"label": "Compares sorted or counted", "contains_any": ["sorted(", "Counter"]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('Listen', 'Silent'))", "expected_output": "True"},
        ],
    )


def _python_max_in_list(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"max_in_list_{suffix}"
    return _spec(
        title="Python: Maximum in List",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(numbers) for {course.code}. "
            "Return the largest number in the list. Return None for an empty list."
        ),
        starter_code=f"def {fn}(numbers):\n    # return the maximum value or None\n    pass",
        expected_output=f"{fn}([3, 7, 2, 9]) returns 9.",
        solution_notes="Guard against empty list, then iterate tracking the highest value seen.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Handles empty list", "contains_all": ["None"]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([3, 7, 2, 9]))", "expected_output": "9"},
        ],
    )


def _python_merge_sorted(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"merge_sorted_{suffix}"
    return _spec(
        title="Python: Merge Two Sorted Lists",
        practical_type="python",
        difficulty="intermediate",
        prompt=(
            f"Write {fn}(list1, list2) for {course.code}. "
            "Both input lists are sorted ascending. Return a new merged sorted list."
        ),
        starter_code=f"def {fn}(list1, list2):\n    # return merged sorted list\n    pass",
        expected_output=f"{fn}([1, 3, 5], [2, 4, 6]) returns [1, 2, 3, 4, 5, 6].",
        solution_notes="Use two pointers to walk through both lists, appending the smaller value each time.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Merges without built-in sort", "contains_all": ["return"]},
            {"label": "Handles both lists", "contains_any": ["while ", "for "]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([1, 3, 5], [2, 4, 6]))", "expected_output": str([1, 2, 3, 4, 5, 6]).replace(' ', '')},
        ],
    )


def _python_count_words(course: Course, seed: int) -> dict:
    suffix = _code_suffix(seed)
    fn = f"count_words_{suffix}"
    return _spec(
        title="Python: Count Words in Sentence",
        practical_type="python",
        difficulty="beginner",
        prompt=(
            f"Write {fn}(sentence) for {course.code}. "
            "Return the number of words in the given sentence. Words are separated by spaces."
        ),
        starter_code=f"def {fn}(sentence):\n    # return the word count\n    pass",
        expected_output=f"{fn}('Hello world') returns 2.",
        solution_notes="Use split() to divide the sentence and return the length of the resulting list.",
        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Splits the sentence", "contains_all": [".split("]},
            {"label": "Returns a count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('Hello world'))", "expected_output": "2"},
        ],
    )


def _java_count_scores(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    threshold = _choice([45, 50, 55, 60, 65, 70, 75], seed)
    method = f"countAtLeast{suffix}"
    return _spec(
        title=f"Java: Count Scores At Least {threshold}",
        practical_type="java",
        difficulty=_difficulty(seed),
        prompt=(
            f"Create a Java static method named {method} that accepts int[] scores and "
            f"returns how many scores are greater than or equal to {threshold}."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int[] scores) {{\n"
            f"        // count scores >= {threshold}\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(new int[]{{40, {threshold}, {threshold + 12}}}) returns 2.",
        solution_notes="Use a loop over the array, increment a counter, and return it.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "int[]"]},
            {"label": "Uses the score threshold", "contains_any": [f">= {threshold}", f">={threshold}"]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        int[] s = {{{40}, {threshold}, {threshold + 12}}};\n        System.out.println(Practice.{method}(s));\n    }}\n}}", "expected_output": "2"},
        ],
    )


def _java_average_scores(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"averageScores{suffix}"
    return _spec(
        title="Java: Average Score Array",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts int[] scores and "
            "returns the average as a double. Return 0.0 for an empty array."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(int[] scores) {{\n"
            "        return 0.0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(new int[]{{60, 75, 90}}) returns 75.0.",
        solution_notes="Check scores.length first, sum with a loop, and divide by a double value.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "double", "int[]"]},
            {"label": "Uses array length", "contains_all": ["length"]},
            {"label": "Avoids integer-only average", "contains_any": ["/ 0.0", "/ (double)", "/(double)", ".0"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] s = {60, 75, 90}; System.out.println(Practice.' + method + '(s));' + '\n    }\n}', "expected_output": "75.0"},
        ],
    )


def _java_format_course(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"formatCourse{suffix}"
    return _spec(
        title="Java: Format Course Label",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(String code, String title) "
            "that returns 'CODE - Title' with the code uppercase."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(String code, String title) {{\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}("{course.code.lower()}", "{course.title}") returns "{course.code} - {course.title}".',
        solution_notes="Use code.toUpperCase() and concatenate the separator and title.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "String"]},
            {"label": "Uppercases the code", "contains_all": [".toUpperCase("]},
            {"label": "Returns a label", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'System.out.println(Practice.' + method + '("csc101", "Test"));' + '\n    }\n}', "expected_output": "CSC101 - Test"},
        ],
    )


def _java_find_index(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"findStudent{suffix}"
    return _spec(
        title="Java: Find Student Index",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method}(String[] students, String target) "
            "that returns the index of target, or -1 when not found."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(String[] students, String target) {{\n"
            "        return -1;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new String[]{{"Amina", "Bala"}}, "Bala") returns 1.',
        solution_notes="Loop through indexes and compare each name to target with equals.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "String[]"]},
            {"label": "Compares strings safely", "contains_all": [".equals"]},
            {"label": "Handles missing values", "contains_all": ["-1"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'String[] s = {"Amina", "Bala"}; System.out.println(Practice.' + method + '(s, "Bala"));' + '\n    }\n}', "expected_output": "1"},
        ],
    )


def _java_highest_value(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"highestValue{suffix}"
    return _spec(
        title="Java: Highest Value",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method}(int[] values) that returns the highest "
            "number in the array. Return 0 when the array is empty."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int[] values) {{\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(new int[]{{14, 22, 9}}) returns 22.",
        solution_notes="Handle the empty case, keep a current maximum, and update it inside a loop.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]"]},
            {"label": "Loops through values", "contains_any": ["for ", "while "]},
            {"label": "Returns the maximum", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] v = {14, 22, 9}; System.out.println(Practice.' + method + '(v));' + '\n    }\n}', "expected_output": "22"},
        ],
    )


def _java_contains_topic(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"containsTopic{suffix}"
    return _spec(
        title="Java: Contains Topic",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(String[] topics, String target) "
            "that returns true when target appears in topics, ignoring case."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static boolean {method}(String[] topics, String target) {{\n"
            "        return false;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new String[]{{"SQL", "Python"}}, "sql") returns true.',
        solution_notes="Loop over topics and compare with equalsIgnoreCase.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "boolean"]},
            {"label": "Ignores case", "contains_all": [".equalsIgnoreCase("]},
            {"label": "Returns true or false", "contains_any": ["true", "false"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'String[] t = {"SQL", "Python"}; System.out.println(Practice.' + method + '(t, "sql"));' + '\n    }\n}', "expected_output": "true"},
        ],
    )


def _java_palindrome(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"isPalindrome{suffix}"
    return _spec(
        title="Java: Check Palindrome String",
        practical_type="java",
        difficulty=_difficulty(seed),
        prompt=(
            f"Create a Java static method named {method}(String text) for {course.code}. "
            "Return true when the text reads the same forward and backward, ignoring case."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static boolean {method}(String text) {{\n"
            "        return false;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}("Racecar") returns true.',
        solution_notes="Convert to lowercase, then loop from both ends comparing characters.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "boolean", "String"]},
            {"label": "Ignores case", "contains_all": [".toLowerCase("]},
            {"label": "Compares characters", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'System.out.println(Practice.' + method + '("Racecar"));' + '\n    }\n}', "expected_output": "true"},
        ],
    )


def _java_reverse_string(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"reverseString{suffix}"
    return _spec(
        title="Java: Reverse String",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(String text) for {course.code}. "
            "Return the string in reverse order. Use a loop, not StringBuilder.reverse()."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(String text) {{\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}("hello") returns "olleh".',
        solution_notes="Build a new string by iterating backwards through characters with charAt.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "String"]},
            {"label": "Uses a loop", "contains_any": ["for ", "while "]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'System.out.println(Practice.' + method + '("hello"));' + '\n    }\n}', "expected_output": "olleh"},
        ],
    )


def _java_two_sum(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    target = _choice([7, 9, 10, 12, 15, 18], seed)
    method = f"twoSum{suffix}"
    return _spec(
        title=f"Java: Two Sum Equals {target}",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method}(int[] numbers, int target). "
            f"Return an int[] with the two indices whose values add to {target}. "
            "Assume exactly one solution exists."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int[] {method}(int[] numbers, int target) {{\n"
            "        return new int[]{0, 0};\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new int[]{{2, 7, 11}}, 9) returns [0, 1].',
        solution_notes="Use a HashMap to store values and their indices for a single pass solution.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]", "target"]},
            {"label": "Uses a HashMap", "contains_all": ["HashMap"]},
            {"label": "Returns an int array", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] n = {2, 7, 11}; int[] r = Practice.' + method + '(n, 9); System.out.println(r[0] + " " + r[1]);' + '\n    }\n}', "expected_output": "0 1"},
        ],
    )


def _java_fizzbuzz(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"fizzBuzz{suffix}"
    return _spec(
        title="Java: FizzBuzz",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(int n). "
            "Return a String[] where numbers 1 to n are replaced with 'Fizz' (multiples of 3), "
            "'Buzz' (multiples of 5), or 'FizzBuzz' (both)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String[] {method}(int n) {{\n"
            "        return new String[0];\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(5) returns ["1", "2", "Fizz", "4", "Buzz"].',
        solution_notes="Create a String array, loop with modulo checks, and fill each position.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "String[]"]},
            {"label": "Uses modulo", "contains_all": ["%"]},
            {"label": "Returns array", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'String[] r = Practice.' + method + '(5); System.out.println(String.join(" ", r));' + '\n    }\n}', "expected_output": "1 2 Fizz 4 Buzz"},
        ],
    )


def _java_count_vowels(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"countVowels{suffix}"
    return _spec(
        title="Java: Count Vowels",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(String text) for {course.code}. "
            "Return the number of vowels (a, e, i, o, u) in the text, ignoring case."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(String text) {{\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}("OpenED") returns 3.',
        solution_notes="Loop through characters, convert to lowercase, and check against vowels.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int", "String"]},
            {"label": "Ignores case", "contains_all": [".toLowerCase("]},
            {"label": "Returns count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'System.out.println(Practice.' + method + '("OpenED"));' + '\n    }\n}', "expected_output": "3"},
        ],
    )


def _java_even_numbers(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"evenNumbers{suffix}"
    return _spec(
        title="Java: Filter Even Numbers",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(int[] numbers) for {course.code}. "
            "Return a new int[] containing only the even numbers from the input."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int[] {method}(int[] numbers) {{\n"
            "        return new int[0];\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new int[]{{1, 2, 3, 4}}) returns [2, 4].',
        solution_notes="First count evens, create an array of that size, then fill it in a second pass.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]"]},
            {"label": "Checks even numbers", "contains_all": ["%"]},
            {"label": "Returns array", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] r = Practice.' + method + '(new int[]{1, 2, 3, 4, 5}); System.out.println(r[0] + " " + r[1]);' + '\n    }\n}', "expected_output": "2 4"},
        ],
    )


def _java_second_largest(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"secondLargest{suffix}"
    return _spec(
        title="Java: Second Largest Number",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method}(int[] numbers) for {course.code}. "
            "Return the second largest value. Return 0 when there are fewer than 2 numbers."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int[] numbers) {{\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new int[]{{10, 20, 30}}) returns 20.',
        solution_notes="Track largest and second largest values in a single pass.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]"]},
            {"label": "Handles edge case", "contains_all": ["length"]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] n = {10, 20, 30}; System.out.println(Practice.' + method + '(n));' + '\n    }\n}', "expected_output": "20"},
        ],
    )


def _java_factorial(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"factorial{suffix}"
    return _spec(
        title="Java: Calculate Factorial",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(int n) for {course.code}. "
            "Return the factorial of n using a loop. Return 1 when n is 0."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int n) {{\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(5) returns 120.',
        solution_notes="Use a for loop from 1 to n, multiplying into an accumulated result.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int"]},
            {"label": "Uses a loop", "contains_any": ["for ", "while "]},
            {"label": "Returns result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'System.out.println(Practice.' + method + '(5));' + '\n    }\n}', "expected_output": "120"},
        ],
    )


def _java_positive_count(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"positiveCount{suffix}"
    return _spec(
        title="Java: Count Positive Numbers",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(int[] numbers) for {course.code}. "
            "Return how many numbers in the array are greater than zero."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int[] numbers) {{\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new int[]{{-5, 0, 3, 8}}) returns 2.',
        solution_notes="Loop through the array, increment a counter for each value greater than 0.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]"]},
            {"label": "Compares to zero", "contains_all": ["> 0"]},
            {"label": "Returns count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] n = {-5, 0, 3, 8}; System.out.println(Practice.' + method + '(n));' + '\n    }\n}', "expected_output": "2"},
        ],
    )


def _java_anagram_check(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"isAnagram{suffix}"
    return _spec(
        title="Java: Anagram Check",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method}(String word1, String word2) for {course.code}. "
            "Return true when both words contain the same letters (ignoring case)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static boolean {method}(String word1, String word2) {{\n"
            "        return false;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}("Listen", "Silent") returns true.',
        solution_notes="Convert both to lowercase, sort the character arrays, and compare.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "boolean"]},
            {"label": "Ignores case", "contains_all": [".toLowerCase("]},
            {"label": "Compares sorted arrays", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'System.out.println(Practice.' + method + '("Listen", "Silent"));' + '\n    }\n}', "expected_output": "true"},
        ],
    )


def _java_max_in_array(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"maxInArray{suffix}"
    return _spec(
        title="Java: Maximum in Array",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(int[] numbers) for {course.code}. "
            "Return the largest value. Return 0 for an empty array."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int[] numbers) {{\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new int[]{{3, 7, 2, 9}}) returns 9.',
        solution_notes="Check array length, then loop tracking the maximum value.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]"]},
            {"label": "Handles empty array", "contains_all": ["length"]},
            {"label": "Returns max", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] n = {3, 7, 2, 9}; System.out.println(Practice.' + method + '(n));' + '\n    }\n}', "expected_output": "9"},
        ],
    )


def _java_merge_sorted(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"mergeSorted{suffix}"
    return _spec(
        title="Java: Merge Two Sorted Arrays",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method}(int[] a, int[] b) for {course.code}. "
            "Both arrays are sorted ascending. Return a new merged sorted array."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int[] {method}(int[] a, int[] b) {{\n"
            "        return new int[0];\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(new int[]{{1, 3, 5}}, new int[]{{2, 4, 6}}) returns [1, 2, 3, 4, 5, 6].',
        solution_notes="Use two indexes to walk both arrays, picking the smaller value at each step.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]"]},
            {"label": "Merges with loop", "contains_any": ["for ", "while "]},
            {"label": "Returns array", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] r = Practice.' + method + '(new int[]{1, 3, 5}, new int[]{2, 4, 6}); for (int v : r) System.out.print(v + " ");' + '\n    }\n}', "expected_output": "1 2 3 4 5 6"},
        ],
    )


def _java_count_words(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"countWords{suffix}"
    return _spec(
        title="Java: Count Words in String",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method}(String sentence) for {course.code}. "
            "Return the number of words separated by spaces."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(String sentence) {{\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}("Hello world") returns 2.',
        solution_notes="Use split() on the space character and return the length of the resulting array.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int", "String"]},
            {"label": "Splits sentence", "contains_all": [".split("]},
            {"label": "Returns count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'System.out.println(Practice.' + method + '("Hello world"));' + '\n    }\n}', "expected_output": "2"},
        ],
    )


def _java_fibonacci(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    limit = _choice([10, 12, 15, 18, 20], seed)
    method = f"fibonacci{suffix}"
    return _spec(
        title=f"Java: First {limit} Fibonacci Numbers",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method}(int n). "
            f"Return an int[] with the first n Fibonacci numbers. n will be at least 1."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int[] {method}(int n) {{\n"
            "        return new int[0];\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}(6) returns [0, 1, 1, 2, 3, 5].',
        solution_notes="Create an array of size n, set first two elements, then fill the rest with a loop.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "int[]"]},
            {"label": "Creates Fibonacci sequence", "contains_all": ["return"]},
            {"label": "Uses a loop", "contains_any": ["for ", "while "]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": 'public class Main {\n    public static void main(String[] args) {\n        ' + 'int[] r = Practice.' + method + '(6); for (int v : r) System.out.print(v + " ");' + '\n    }\n}', "expected_output": "0 1 1 2 3 5"},
        ],
    )


def _sql_select_scores(course: Course, seed: int) -> dict:
    table = f"{_sql_slug(course.code)}_results"
    threshold = _choice([50, 55, 60, 65, 70, 75], seed)
    return _spec(
        title=f"Database: Select Scores Above {threshold}",
        practical_type="database",
        difficulty="beginner",
        prompt=(
            f"Write an SQL query for {table}(student_id, student_name, score, submitted_at). "
            f"Return student_name and score for rows where score is at least {threshold}, highest score first."
        ),
        starter_code=f"SELECT \nFROM {table}\nWHERE \nORDER BY ;",
        expected_output=f"Rows with score >= {threshold}, ordered by score descending.",
        solution_notes="Use SELECT student_name, score, WHERE score >= the target, and ORDER BY score DESC.",
        checks=[
            {"label": "Selects required columns", "contains_all": ["select", "student_name", "score"], "case_sensitive": False},
            {"label": "Filters by score", "contains_any": [f"score >= {threshold}", f"score>={threshold}"], "case_sensitive": False},
            {"label": "Orders highest first", "contains_all": ["order by", "desc"], "case_sensitive": False},
        ],
    )


def _sql_group_enrolments(course: Course, seed: int) -> dict:
    table = f"{_sql_slug(course.code)}_enrolments"
    return _spec(
        title="Database: Count Active Enrolments",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL query for {table}(course_code, student_id, status). "
            "Return each course_code and the number of active students, grouped by course_code."
        ),
        starter_code=f"SELECT \nFROM {table}\nWHERE status = 'active'\nGROUP BY ;",
        expected_output="One row per course_code with an active student count.",
        solution_notes="Use COUNT(*), filter status = 'active', and GROUP BY course_code.",
        checks=[
            {"label": "Uses an aggregate", "contains_all": ["count"], "case_sensitive": False},
            {"label": "Filters active rows", "contains_all": ["status", "active"], "case_sensitive": False},
            {"label": "Groups by course", "contains_all": ["group by", "course_code"], "case_sensitive": False},
        ],
    )


def _sql_join_attempts(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Join Students and Attempts",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL query joining {prefix}_students(id, full_name) to "
            f"{prefix}_attempts(student_id, practical_title, score). Return full_name, practical_title, and score."
        ),
        starter_code=(
            f"SELECT \nFROM {prefix}_students s\n"
            f"JOIN {prefix}_attempts a ON ;"
        ),
        expected_output="Rows showing each student's name beside their practical title and score.",
        solution_notes="Join students.id to attempts.student_id and select columns from both tables.",
        checks=[
            {"label": "Uses a join", "contains_all": ["join"], "case_sensitive": False},
            {"label": "Connects matching ids", "contains_all": ["student_id"], "case_sensitive": False},
            {"label": "Returns required fields", "contains_all": ["full_name", "practical_title", "score"], "case_sensitive": False},
        ],
    )


def _sql_create_score_table(course: Course, seed: int) -> dict:
    table = f"{_sql_slug(course.code)}_practical_scores"
    return _spec(
        title="Database: Create Practical Scores Table",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write SQL to create a table named {table} with id as primary key, student_id, "
            "practical_title, score, and submitted_at. Add a score constraint from 0 to 100."
        ),
        starter_code=f"CREATE TABLE {table} (\n\n);",
        expected_output="A table that stores practical scores with a primary key and score range constraint.",
        solution_notes="Use CREATE TABLE, a PRIMARY KEY, NOT NULL columns, and a CHECK constraint for score.",
        checks=[
            {"label": "Creates the table", "contains_all": ["create table", table], "case_sensitive": False},
            {"label": "Defines a primary key", "contains_all": ["primary key"], "case_sensitive": False},
            {"label": "Constrains score range", "contains_all": ["check", "score"], "case_sensitive": False},
        ],
    )


def _sql_update_bonus(course: Course, seed: int) -> dict:
    table = f"{_sql_slug(course.code)}_results"
    bonus = _choice([2, 3, 4, 5], seed)
    return _spec(
        title=f"Database: Apply {bonus}-Point Bonus",
        practical_type="database",
        difficulty="beginner",
        prompt=(
            f"Write an SQL UPDATE for {table}(course_code, score, status). "
            f"Add {bonus} points to score only for rows where course_code = '{course.code}' and status = 'submitted'."
        ),
        starter_code=f"UPDATE {table}\nSET \nWHERE ;",
        expected_output=f"Only submitted {course.code} rows have score increased by {bonus}.",
        solution_notes="Use UPDATE, SET score = score + bonus, and a WHERE clause with both conditions.",
        checks=[
            {"label": "Uses UPDATE", "contains_all": ["update", table], "case_sensitive": False},
            {"label": "Adds the bonus", "contains_any": [f"score + {bonus}", f"score+{bonus}"], "case_sensitive": False},
            {"label": "Limits affected rows", "contains_all": ["where", "course_code", "status"], "case_sensitive": False},
        ],
    )


def _sql_having_average(course: Course, seed: int) -> dict:
    table = f"{_sql_slug(course.code)}_attempts"
    threshold = _choice([50, 55, 60, 65, 70], seed)
    return _spec(
        title=f"Database: Average Score At Least {threshold}",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL query for {table}(student_id, practical_title, score). "
            f"Return each student_id whose average score is at least {threshold}."
        ),
        starter_code=f"SELECT \nFROM {table}\nGROUP BY \nHAVING ;",
        expected_output=f"Student IDs with AVG(score) >= {threshold}.",
        solution_notes="Group by student_id and use HAVING AVG(score) >= the target.",
        checks=[
            {"label": "Calculates an average", "contains_all": ["avg", "score"], "case_sensitive": False},
            {"label": "Groups by student", "contains_all": ["group by", "student_id"], "case_sensitive": False},
            {"label": "Filters groups", "contains_all": ["having"], "case_sensitive": False},
        ],
    )


def _sql_create_index(course: Course, seed: int) -> dict:
    table = f"{_sql_slug(course.code)}_attempts"
    index_name = f"idx_{_sql_slug(course.code)}_student_completed"
    return _spec(
        title="Database: Create Attempt Lookup Index",
        practical_type="database",
        difficulty="advanced",
        prompt=(
            f"Write SQL to create an index named {index_name} on {table}. "
            "The index should help queries that filter by student_id and sort by completed_at."
        ),
        starter_code=f"CREATE INDEX {index_name}\nON {table} ();",
        expected_output="An index on student_id and completed_at.",
        solution_notes="Use CREATE INDEX with both student_id and completed_at in the column list.",
        checks=[
            {"label": "Creates the named index", "contains_all": ["create index", index_name], "case_sensitive": False},
            {"label": "Targets the attempt table", "contains_all": ["on", table], "case_sensitive": False},
            {"label": "Includes lookup columns", "contains_all": ["student_id", "completed_at"], "case_sensitive": False},
        ],
    )


# --- COSC 211 curriculum-aligned Java builders ---

def _java_print_triangle(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    rows = _choice([4, 5, 6], seed)
    method = f"printTriangle{suffix}"
    lines = []
    num = 1
    for r in range(1, rows + 1):
        line = " ".join(str(num + i) for i in range(r))
        lines.append(line)
        num += r
    expected = "\n".join(lines)
    return _spec(
        title="Java: Print Number Triangle Pattern",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that takes int n and returns a String. "
            f"The result should contain n rows of a number triangle where row r has r consecutive numbers. "
            "Rows are separated by newlines."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(int n) {{\n"
            "        StringBuilder sb = new StringBuilder();\n"
            "        int num = 1;\n"
            "        for (int r = 1; r <= n; r++) {\n"
            "            // build row r with r numbers\n"
            "        }\n"
            "        return sb.toString().trim();\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({rows}) returns the triangle pattern.",
        solution_notes="Use nested loops: outer loop for rows, inner loop for columns. Track the next number with a counter.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String"]},
            {"label": "Uses nested loops", "contains_all": ["for ", "for "]},
            {"label": "Builds a string", "contains_any": ["StringBuilder", "StringBuffer"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({rows}));\n    }}\n}}", "expected_output": expected},
        ],
    )


def _java_email_parser(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"extractUsername{suffix}"
    return _spec(
        title="Java: Extract Email Username",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method} that accepts a String email "
            "and returns the username portion (everything before @). "
            "Return the original string if no @ is found."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(String email) {{\n"
            "        // find @ and return substring before it\n"
            "        return email;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(\"bmghandi@csee.kfupm.edu.sa\") returns \"bmghandi\".",
        solution_notes="Use indexOf('@') and substring() to extract the username portion.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String"]},
            {"label": "Uses indexOf", "contains_all": ["indexOf"]},
            {"label": "Uses substring", "contains_all": ["substring"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}(\"bmghandi@csee.kfupm.edu.sa\"));\n    }}\n}}", "expected_output": "bmghandi"},
        ],
    )


def _java_password_gen(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"makePassword{suffix}"
    return _spec(
        title="Java: Generate Password from Name",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "String firstName, String middleName, String lastName, int age. "
            "Return a password formed from: first initial of each name (lowercase) "
            "plus the age. If a middle name initial is not available use 'x'."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(String first, String mid, String last, int age) {{\n"
            "        // build password from initials + age\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(\"Amr\", \"Samir\", \"Al-Ibrahim\", 20) returns \"asx20\".",
        solution_notes="Use charAt(0), toLowerCase(), and concatenation. Handle short middle names with substring or a default.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String", "int age"]},
            {"label": "Uses charAt or substring", "contains_any": ["charAt", "substring"]},
            {"label": "Uses toLowerCase", "contains_all": ["toLowerCase"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}(\"Amr\", \"Samir\", \"Al-Ibrahim\", 20));\n    }}\n}}", "expected_output": "asx20"},
        ],
    )


def _java_box_surface(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"boxSurfaceArea{suffix}"
    length = _choice([5, 10, 15, 20], seed)
    width = _choice([3, 4, 6, 8], seed + 1)
    height = _choice([2, 5, 7, 9], seed + 2)
    expected = str(2 * (length * width + length * height + width * height)) + ".0"
    return _spec(
        title="Java: Box Surface Area",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double length, double width, double height and "
            "returns the surface area: 2(lw + lh + wh)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double length, double width, double height) {{\n"
            "        return 0.0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({length}.0, {width}.0, {height}.0) returns {expected}.",
        solution_notes="Compute 2 * (length * width + length * height + width * height).",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "double"]},
            {"label": "Calculates surface area", "contains_all": ["2", "length", "width", "height"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({length}.0, {width}.0, {height}.0));\n    }}\n}}", "expected_output": expected},
        ],
    )


def _java_bank_account(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"processAccount{suffix}"
    deposit = _choice([100, 250, 500, 1000], seed)
    withdraw = _choice([30, 50, 75, 100], seed + 1)
    balance = 500 + deposit - withdraw
    return _spec(
        title="Java: Bank Account Transaction",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double initialBalance, double depositAmount, double withdrawalAmount. "
            "Add the deposit to the balance, subtract the withdrawal, and return the final balance. "
            "If withdrawal exceeds the balance after deposit, return -1.0 (overdraft)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double balance, double deposit, double withdrawal) {{\n"
            "        // process deposit and withdrawal, check overdraft\n"
            "        return 0.0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(500.0, {deposit}.0, {withdraw}.0) returns {(500 + deposit - withdraw)}.0.",
        solution_notes="Add deposit, check if withdrawal exceeds new balance, subtract if valid or return -1.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "double"]},
            {"label": "Checks for overdraft", "contains_all": ["-1"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}(500.0, {deposit}.0, {withdraw}.0));\n    }}\n}}", "expected_output": str(balance) + ".0"},
        ],
    )


def _java_student_average(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"quizAverage{suffix}"
    q1 = _choice([65, 70, 75, 80, 85], seed)
    q2 = _choice([70, 75, 78, 82, 88], seed + 1)
    q3 = _choice([60, 68, 72, 79, 84], seed + 2)
    avg = (q1 + q2 + q3) / 3.0
    fmt_avg = f"{avg:.1f}" if avg != int(avg) else f"{int(avg)}.0"
    return _spec(
        title="Java: Student Quiz Average",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double quiz1, double quiz2, double quiz3 and returns the average of the three quizzes."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double q1, double q2, double q3) {{\n"
            "        return 0.0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({q1}.0, {q2}.0, {q3}.0) returns {fmt_avg}.",
        solution_notes="Add all three scores and divide by 3.0 (not 3) to get a decimal result.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "double"]},
            {"label": "Returns a double average", "contains_all": ["/ 3.0", "/3.0", "/ 3d", "/3d"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({q1}.0, {q2}.0, {q3}.0));\n    }}\n}}", "expected_output": fmt_avg},
        ],
    )


def _java_quadratic_roots(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"classifyRoots{suffix}"
    a = _choice([1, 2, 3], seed)
    b = _choice([5, 6, 7, 8], seed + 1)
    c = _choice([2, 3, 1], seed + 2)
    disc = b * b - 4 * a * c
    if disc > 0:
        result = "real and distinct"
    elif disc == 0:
        result = "real and equal"
    else:
        result = "complex"
    return _spec(
        title="Java: Classify Quadratic Roots",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double a, double b, double c representing ax² + bx + c = 0. "
            "Return \"real and distinct\" if discriminant > 0, "
            "\"real and equal\" if discriminant == 0, or \"complex\" if discriminant < 0."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(double a, double b, double c) {{\n"
            "        double d = b * b - 4 * a * c;\n"
            "        // classify based on discriminant\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({a}.0, {b}.0, {c}.0) returns \"{result}\".",
        solution_notes="Calculate discriminant, use if-else to classify based on whether it's positive, zero, or negative.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String"]},
            {"label": "Calculates discriminant", "contains_all": ["b * b", "- 4", "a * c"]},
            {"label": "Uses if-else logic", "contains_any": ["if", "else"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({a}.0, {b}.0, {c}.0));\n    }}\n}}", "expected_output": result},
        ],
    )


def _java_arithmetic_progression(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"apSum{suffix}"
    a = _choice([2, 3, 5], seed)
    d = _choice([2, 3, 4], seed + 1)
    n = _choice([8, 10, 12], seed + 2)
    tn = a + (n - 1) * d
    sn = n * (a + tn) / 2
    fmt_sn = f"{sn:.0f}" if sn == int(sn) else f"{sn}"
    return _spec(
        title="Java: Arithmetic Progression Sum",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double firstTerm, double commonDiff, int n. "
            "Return the sum of the first n terms of an arithmetic progression. "
            "Formula: Tn = a + (n-1)d, Sn = (n/2)(a + Tn)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double a, double d, int n) {{\n"
            "        // compute nth term and sum\n"
            "        return 0.0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({a}.0, {d}.0, {n}) returns {fmt_sn}.",
        solution_notes="Calculate Tn = a + (n-1)*d, then Sn = n * (a + Tn) / 2.0.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "double", "int n"]},
            {"label": "Calculates nth term", "contains_all": ["- 1", "* d", "(n"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({a}.0, {d}.0, {n}));\n    }}\n}}", "expected_output": fmt_sn},
        ],
    )


def _java_grade_stats(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"gradeStats{suffix}"
    threshold = _choice([50, 60], seed)
    return _spec(
        title="Java: Grade Pass/Fail Statistics",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            f"int[] scores and returns a String formatted as 'Pass=X Fail=Y' where "
            f"passing is >= {threshold} and failing is < {threshold}."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(int[] scores) {{\n"
            "        int pass = 0, fail = 0;\n"
            "        // count pass and fail\n"
            "        return \"Pass=\" + pass + \" Fail=\" + fail;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(new int[]{{45, {threshold}, {threshold + 10}, 30, 80}}) returns \"Pass=2 Fail=3\".",
        solution_notes="Loop through the array, increment pass or fail based on threshold comparison.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String", "int[]"]},
            {"label": "Counts pass and fail", "contains_all": ["pass", "fail"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        int[] s = {{45, {threshold}, {threshold + 10}, 30, 80}};\n        System.out.println(Practice.{method}(s));\n    }}\n}}", "expected_output": "Pass=2 Fail=3"},
        ],
    )


def _java_investment_future(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"futureValue{suffix}"
    p = _choice([1000, 2000, 5000], seed)
    r = _choice([5, 7, 10], seed + 1)
    n = _choice([2, 3, 5], seed + 2)
    a = p * (1 + r / 100.0) ** n
    # compare within tolerance
    fmt_a = f"{a:.2f}"
    return _spec(
        title="Java: Investment Future Value",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double principal, double ratePercent, int years. "
            "Return the future value using A = P(1 + r/100)^n. "
            "Use Math.pow for exponentiation."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double p, double r, int n) {{\n"
            "        // A = p * (1 + r/100)^n\n"
            "        return 0.0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({p}.0, {r}.0, {n}) returns approximately {fmt_a}.",
        solution_notes="Compute 1 + r/100, use Math.pow(..., n), multiply by P.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "double"]},
            {"label": "Uses Math.pow", "contains_all": ["Math.pow", "Math .pow"]},
            {"label": "Calculates correct formula", "contains_all": ["/ 100", "/100"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.printf(\"%.2f\", Practice.{method}({p}.0, {r}.0, {n}));\n    }}\n}}", "expected_output": fmt_a},
        ],
    )


# --- Labs 06-10: Overloading, Arrays, 2D Arrays, Recursion ---

def _java_employee_deductions(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"processSalary{suffix}"
    salary = _choice([5000, 7500, 10000, 15000], seed)
    d1 = _choice([200, 350, 500], seed + 1)
    d2 = _choice([100, 150, 250], seed + 2)
    result = salary - d1 - d2
    return _spec(
        title="Java: Overloaded Salary Deductions",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that is overloaded. "
            "Version 1: accepts double salary, double ded1 — returns salary - ded1. "
            "Version 2: accepts double salary, double ded1, double ded2 — returns salary - ded1 - ded2. "
            "Both versions return the remaining salary."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double salary, double ded1) {{\n"
            "        return salary - ded1;\n"
            "    }\n"
            f"    public static double {method}(double salary, double ded1, double ded2) {{\n"
            "        return 0.0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({salary}.0, {d1}.0, {d2}.0) returns {result}.0.",
        solution_notes="Create two methods with same name but different parameter counts.",
        checks=[
            {"label": "Defines overloaded methods", "contains_all": [method, "double", "double", "double"]},
            {"label": "Has two versions", "contains_any": [f"ded2", "ded3"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({salary}.0, {d1}.0, {d2}.0));\n    }}\n}}", "expected_output": f"{result}.0"},
        ],
    )


def _java_author_tostring(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"formatAuthor{suffix}"
    names = ["Aliyu Garba", "Aisha Bello", "Musa Ibrahim"]
    emails = ["galiyu@abu.edu.ng", "aisha@abu.edu.ng", "musa@abu.edu.ng"]
    genders = ["m", "f", "m"]
    idx = seed % 3
    name, email, gender = names[idx], emails[idx], genders[idx]
    expected = f"{name} ({gender}) at {email}"
    return _spec(
        title="Java: Format Author with toString Style",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "String name, String email, char gender. Return a string "
            "formatted as 'Name (gender) at email'."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(String name, String email, char gender) {{\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}("{name}", "{email}", \'{gender}\') returns "{expected}".',
        solution_notes="Use string concatenation with parentheses and ' at ' between parts.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String"]},
            {"label": "Formats correctly", "contains_all": [" + ", "(", "at"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}(\"{name}\", \"{email}\", '{gender}'));\n    }}\n}}", "expected_output": expected},
        ],
    )


def _java_vector_product(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"dotProduct{suffix}"
    return _spec(
        title="Java: Vector Dot Product",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double[] a and double[] b and returns the dot product "
            "(sum of a[i] * b[i] for each index). Assume arrays are the same length."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double[] a, double[] b) {{\n"
            "        double sum = 0;\n"
            "        // compute dot product\n"
            "        return sum;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(new double[]{{5, 2, -3}}, new double[]{{2, 3, 5}}) returns 1.0.",
        solution_notes="Loop through indices, multiply a[i] * b[i], accumulate the sum.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "double", "double[]"]},
            {"label": "Loops over arrays", "contains_all": ["for", "length"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        double[] a = {{5, 2, -3}};\n        double[] b = {{2, 3, 5}};\n        System.out.println(Practice.{method}(a, b));\n    }}\n}}", "expected_output": "1.0"},
        ],
    )


def _java_profit_stats(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"profitStats{suffix}"
    return _spec(
        title="Java: Array Profit Statistics",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double[] profits and returns a String formatted as "
            "'Max=X Min=Y Sum=Z Avg=W' with two decimal places."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(double[] profits) {{\n"
            "        // compute and return formatted statistics\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(new double[]{{5000, 2005, 3020, 5057.8, 4500}}) returns a formatted stats string.",
        solution_notes="Find min and max by comparison, sum with a loop, average = sum / length. Use printf or String.format.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String", "double[]"]},
            {"label": "Finds min and max", "contains_all": ["min", "max"]},
            {"label": "Calculates average", "contains_all": ["avg", "sum", "length"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        double[] p = {{5000, 2005, 3020, 5057.8, 4500}};\n        System.out.println(Practice.{method}(p));\n    }}\n}}", "expected_output": "Max=5057.80 Min=2005.00 Sum=19582.80 Avg=3916.56"},
        ],
    )


def _java_matrix_add(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"sumMatrices{suffix}"
    tc = (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        int[][] a = {{1, 2, 3}, {4, 5, 6}};\n"
        "        int[][] b = {{7, 8, 9}, {10, 11, 12}};\n"
        f"        System.out.println(Practice.{method}(a, b));\n"
        "    }\n"
        "}"
    )
    return _spec(
        title="Java: Add Two Matrices",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "int[][] a and int[][] b and returns a String. "
            "Add corresponding elements and build a formatted string "
            "with each row of the sum on a new line (tabs between values)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(int[][] a, int[][] b) {{\n"
            "        StringBuilder sb = new StringBuilder();\n"
            "        // add and format resulting matrix\n"
            "        return sb.toString().trim();\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method} adds two 3x2 matrices element-wise.",
        solution_notes="Use nested loops, sum a[i][j] + b[i][j], append to StringBuilder with tabs and newlines.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String", "int[][]"]},
            {"label": "Uses nested loops", "contains_all": ["for", "for"]},
            {"label": "Builds string output", "contains_any": ["StringBuilder", "StringBuffer"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": tc, "expected_output": "8\t10\t12\n14\t16\t18"},
        ],
    )


def _java_magic_square(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"isMagic{suffix}"
    tc = (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        int[][] m = {{16, 3, 2, 13}, {5, 10, 11, 8}, {9, 6, 7, 12}, {4, 15, 14, 1}};\n"
        f"        System.out.println(Practice.{method}(m));\n"
        "    }\n"
        "}"
    )
    return _spec(
        title="Java: Check Magic Square",
        practical_type="java",
        difficulty="advanced",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "int[][] matrix and returns 'magic' if it is a magic square "
            "(all rows, columns, and diagonals sum to the same value) "
            "or 'not magic' otherwise. Assume a square matrix."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(int[][] matrix) {{\n"
            "        // check if all rows, columns, diagonals have same sum\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method} on a 4x4 Lo Shu magic square returns 'magic'.",
        solution_notes="Compute first row sum, then compare each row, column, and both diagonals against it.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String", "int[][]"]},
            {"label": "Sums rows and columns", "contains_all": ["row", "col", "sum"]},
            {"label": "Checks diagonals", "contains_all": ["diag"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": tc, "expected_output": "magic"},
        ],
    )


def _java_recursive_factorial(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"fact{suffix}"
    n = _choice([5, 6, 7, 8, 9, 10], seed)
    fact = 1
    for i in range(2, n + 1):
        fact *= i
    return _spec(
        title="Java: Recursive Factorial",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that recursively "
            f"computes the factorial of n (n >= 0). Base case: factorial(0) = 1. "
            "Recursive case: factorial(n) = n * factorial(n-1)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int n) {{\n"
            "        if (n <= 1) return 1;\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({n}) returns {fact}.",
        solution_notes="Base case: return 1 when n <= 1. Recursive case: return n * method(n-1).",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "int", "int n"]},
            {"label": "Uses recursion", "contains_all": [method + "(n-1)", method + "(n - 1)"]},
            {"label": "Has a base case", "contains_all": ["return 1"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({n}));\n    }}\n}}", "expected_output": str(fact)},
        ],
    )


def _java_recursive_fibonacci(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"fib{suffix}"
    n = _choice([6, 7, 8, 9, 10], seed)
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    fib = a
    return _spec(
        title="Java: Recursive Fibonacci",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that recursively "
            f"returns the nth Fibonacci number. fib(0)=0, fib(1)=1, "
            "fib(n)=fib(n-1)+fib(n-2) for n > 1."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static int {method}(int n) {{\n"
            "        if (n <= 1) return n;\n"
            "        return 0;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({n}) returns {fib}.",
        solution_notes="Base cases: n<=1 returns n. Recursive: return method(n-1) + method(n-2).",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "int", "int n"]},
            {"label": "Uses recursion", "contains_all": [method + "("]},
            {"label": "Has base cases", "contains_all": ["return n"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({n}));\n    }}\n}}", "expected_output": str(fib)},
        ],
    )


# --- COSC 212 curriculum-aligned Java builders ---

def _java_weighed_item(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"calculatePrice{suffix}"
    unit = _choice([2.5, 3.0, 4.5, 5.0], seed)
    weight = _choice([0.5, 1.0, 1.37, 2.0], seed + 1)
    total = unit * weight
    fmt_total = f"{total:.2f}"
    return _spec(
        title="Java: Weighed Item Price",
        practical_type="java",
        difficulty="beginner",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double unitPrice and double weightKg and returns the total price "
            "(unitPrice * weightKg) formatted to two decimal places using String.format."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(double unitPrice, double weightKg) {{\n"
            "        return \"\";\n"
            "    }\n"
            "}"
        ),
        expected_output=f'{method}({unit}, {weight}) returns "{fmt_total}".',
        solution_notes="Multiply the two values and use String.format('%.2f', result).",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String"]},
            {"label": "Uses String.format", "contains_any": ["String.format", "printf"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({unit}, {weight}));\n    }}\n}}", "expected_output": fmt_total},
        ],
    )


def _java_rental_mileage(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"mileageFee{suffix}"
    kms = _choice([50, 150, 300, 500], seed)
    if kms < 100:
        fee = 0.2 * kms
    elif kms <= 400:
        fee = 0.3 * kms
    else:
        fee = 0.3 * 400 + 0.5 * (kms - 400)
    fmt_fee = f"{fee:.2f}"
    return _spec(
        title="Java: Vehicle Mileage Fee",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "int km and returns the mileage fee as a formatted string with two decimals: "
            "km < 100: 0.2 * km | 100 <= km <= 400: 0.3 * km | km > 400: 0.3*400 + 0.5*(km-400)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static String {method}(int km) {{\n"
            "        double fee;\n"
            "        // calculate based on km range\n"
            "        return String.format(\"%.2f\", fee);\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}({kms}) returns \"{fmt_fee}\".",
        solution_notes="Use if-else to determine the rate tier, compute fee, then format with String.format.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "String", "int km"]},
            {"label": "Uses conditional logic", "contains_all": ["if", "else"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        System.out.println(Practice.{method}({kms}));\n    }}\n}}", "expected_output": fmt_fee},
        ],
    )


def _java_total_payroll(course: Course, seed: int) -> dict:
    suffix = _java_suffix(seed)
    method = f"totalPayroll{suffix}"
    return _spec(
        title="Java: Employee Payroll Total",
        practical_type="java",
        difficulty="intermediate",
        prompt=(
            f"Create a Java static method named {method} that accepts "
            "double[] payRates and int[] hoursWorked and returns the total "
            "payroll (sum of payRates[i] * hoursWorked[i] for each employee)."
        ),
        starter_code=(
            "public class Practice {\n"
            f"    public static double {method}(double[] rates, int[] hours) {{\n"
            "        double total = 0;\n"
            "        // sum all payRate * hours\n"
            "        return total;\n"
            "    }\n"
            "}"
        ),
        expected_output=f"{method}(new double[]{{15.0, 20.0}}, new int[]{{40, 30}}) returns 1200.0.",
        solution_notes="Loop through the array, multiply each pay rate by corresponding hours, accumulate.",
        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "double", "double[]", "int[]"]},
            {"label": "Loops and accumulates", "contains_all": ["for", "+"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\n    public static void main(String[] args) {{\n        double[] rates = {{15.0, 20.0, 25.0}};\n        int[] hours = {{40, 30, 35}};\n        System.out.println(Practice.{method}(rates, hours));\n    }}\n}}", "expected_output": "1775.0"},
        ],
    )


def _spec(
    title: str,
    practical_type: str,
    difficulty: str,
    prompt: str,
    starter_code: str,
    expected_output: str,
    solution_notes: str,
    checks: list[dict],
) -> dict:
    return {
        "title": title,
        "practical_type": practical_type,
        "difficulty": difficulty,
        "prompt": prompt,
        "starter_code": starter_code,
        "expected_output": expected_output,
        "solution_notes": solution_notes,
        "checks": checks,
    }


def _sql_left_join(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Left Join Students and Submissions",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL query that LEFT JOINs {prefix}_students(student_id, full_name) "
            f"to {prefix}_submissions(student_id, score). "
            "Return full_name and score, including students with no submissions (score shows NULL)."
        ),
        starter_code=(
            f"SELECT s.full_name, sub.score\n"
            f"FROM {prefix}_students s\n"
            f"LEFT JOIN {prefix}_submissions sub ON ;"
        ),
        expected_output="All students listed with their submission score (NULL if none).",
        solution_notes="Use LEFT JOIN with a matching condition on student_id.",
        checks=[
            {"label": "Uses LEFT JOIN", "contains_all": ["left join", "left outer join"], "case_sensitive": False},
            {"label": "Joins student tables", "contains_all": ["student_id"], "case_sensitive": False},
            {"label": "Selects required fields", "contains_all": ["full_name", "score"], "case_sensitive": False},
        ],
    )


def _sql_subquery_avg(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Subquery for Above-Average Scores",
        practical_type="database",
        difficulty="advanced",
        prompt=(
            f"Write an SQL query for {prefix}_scores(student_id, score). "
            "Return student_id and score for rows where the score is above the average score. "
            "Use a subquery to compute the average."
        ),
        starter_code=f"SELECT student_id, score\nFROM {prefix}_scores\nWHERE score > (SELECT );",
        expected_output="Students whose score exceeds the overall average.",
        solution_notes="Use a subquery with SELECT AVG(score) FROM the same table.",
        checks=[
            {"label": "Uses a subquery", "contains_all": ["select", "avg"], "case_sensitive": False},
            {"label": "Compares to average", "contains_all": ["score >", "score>"], "case_sensitive": False},
            {"label": "Selects required columns", "contains_all": ["student_id", "score"], "case_sensitive": False},
        ],
    )


def _sql_rank_window(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Rank Students by Score",
        practical_type="database",
        difficulty="advanced",
        prompt=(
            f"Write an SQL query for {prefix}_results(student_id, score). "
            "Return student_id, score, and a rank calculated by score (highest = rank 1). "
            "Use a window function."
        ),
        starter_code=(
            f"SELECT student_id, score, RANK() OVER (ORDER BY ) AS rank\n"
            f"FROM {prefix}_results;"
        ),
        expected_output="Each student ranked from highest to lowest score.",
        solution_notes="Use RANK() or DENSE_RANK() with ORDER BY score DESC in the OVER clause.",
        checks=[
            {"label": "Uses a window function", "contains_all": ["rank() over", "rank()over"], "case_sensitive": False},
            {"label": "Orders by score", "contains_all": ["order by", "score"], "case_sensitive": False},
            {"label": "Selects required columns", "contains_all": ["student_id", "score"], "case_sensitive": False},
        ],
    )


def _sql_case_label(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: CASE Status Labels",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL query for {prefix}_results(student_id, score). "
            "Return student_id, score, and a status_label column: "
            "'Pass' if score >= 50, 'Fail' otherwise. Use a CASE expression."
        ),
        starter_code=(
            f"SELECT student_id, score,\n"
            f"  CASE WHEN THEN 'Pass' ELSE 'Fail' END AS status_label\n"
            f"FROM {prefix}_results;"
        ),
        expected_output="Each row includes a Pass/Fail label based on the score.",
        solution_notes="Use CASE WHEN score >= 50 THEN 'Pass' ELSE 'Fail' END.",
        checks=[
            {"label": "Uses CASE expression", "contains_all": ["case", "when", "then", "end"], "case_sensitive": False},
            {"label": "Checks score threshold", "contains_all": ["score", "50"], "case_sensitive": False},
            {"label": "Selects required columns", "contains_all": ["student_id", "status_label"], "case_sensitive": False},
        ],
    )


def _sql_coalesce_default(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: COALESCE Default Values",
        practical_type="database",
        difficulty="beginner",
        prompt=(
            f"Write an SQL query for {prefix}_profiles(student_id, full_name, bio). "
            "Return student_id, full_name, and bio. When bio is NULL, show 'No bio provided'. "
            "Use COALESCE."
        ),
        starter_code=(
            f"SELECT student_id, full_name, COALESCE(bio, ) AS bio\n"
            f"FROM {prefix}_profiles;"
        ),
        expected_output="NULL bios replaced with a default message.",
        solution_notes="Use COALESCE(bio, 'No bio provided').",
        checks=[
            {"label": "Uses COALESCE", "contains_all": ["coalesce"], "case_sensitive": False},
            {"label": "Handles NULL bios", "contains_all": ["bio"], "case_sensitive": False},
            {"label": "Selects all required columns", "contains_all": ["student_id", "full_name"], "case_sensitive": False},
        ],
    )


def _sql_delete_old(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Delete Old Records",
        practical_type="database",
        difficulty="beginner",
        prompt=(
            f"Write an SQL DELETE statement for {prefix}_logs(id, message, logged_at). "
            "Delete all log entries where logged_at is before '2025-01-01'."
        ),
        starter_code=f"DELETE FROM {prefix}_logs\nWHERE ;",
        expected_output="All log entries before January 1, 2025 are deleted.",
        solution_notes="Use DELETE FROM with a WHERE clause comparing logged_at to the date.",
        checks=[
            {"label": "Uses DELETE", "contains_all": ["delete", prefix], "case_sensitive": False},
            {"label": "Filters by date", "contains_all": ["logged_at", "2025"], "case_sensitive": False},
            {"label": "Uses WHERE clause", "contains_all": ["where"], "case_sensitive": False},
        ],
    )


def _sql_insert_select(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: INSERT INTO SELECT",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL statement to copy high-scoring students from "
            f"{prefix}_results(student_id, score) into {prefix}_honours(student_id, score). "
            "Only insert rows where score is at least 70."
        ),
        starter_code=(
            f"INSERT INTO {prefix}_honours (student_id, score)\n"
            f"SELECT student_id, score\nFROM {prefix}_results\nWHERE ;"
        ),
        expected_output="All high-scoring students are copied into the honours table.",
        solution_notes="Use INSERT INTO ... SELECT ... WHERE score >= 70.",
        checks=[
            {"label": "Uses INSERT INTO", "contains_all": ["insert into"], "case_sensitive": False},
            {"label": "Uses SELECT subquery", "contains_all": ["select"], "case_sensitive": False},
            {"label": "Filters by score", "contains_all": ["score", "70"], "case_sensitive": False},
        ],
    )


def _sql_like_search(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: LIKE Pattern Search",
        practical_type="database",
        difficulty="beginner",
        prompt=(
            f"Write an SQL query for {prefix}_students(student_id, full_name, email). "
            "Return full_name and email where the email address contains 'student' and "
            "the full_name starts with 'A'."
        ),
        starter_code=(
            f"SELECT full_name, email\nFROM {prefix}_students\n"
            f"WHERE email LIKE  AND full_name LIKE ;"
        ),
        expected_output="Students whose email has 'student' and name starts with A.",
        solution_notes="Use LIKE '%student%' for the email condition and LIKE 'A%' for the name.",
        checks=[
            {"label": "Uses LIKE pattern", "contains_all": ["like"], "case_sensitive": False},
            {"label": "Searches email domain", "contains_all": ["%student%"], "case_sensitive": False},
            {"label": "Searches name prefix", "contains_all": ["'A%"], "case_sensitive": False},
        ],
    )


def _sql_count_distinct(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Count Distinct Submissions",
        practical_type="database",
        difficulty="beginner",
        prompt=(
            f"Write an SQL query for {prefix}_submissions(student_id, practical_title, score). "
            "Return the number of distinct students who have submitted at least one practical."
        ),
        starter_code=f"SELECT COUNT(DISTINCT ) AS student_count\nFROM {prefix}_submissions;",
        expected_output="A single number showing how many unique students submitted.",
        solution_notes="Use COUNT(DISTINCT student_id).",
        checks=[
            {"label": "Uses COUNT DISTINCT", "contains_all": ["count", "distinct"], "case_sensitive": False},
            {"label": "Counts student_id", "contains_all": ["student_id"], "case_sensitive": False},
            {"label": "Selects from correct table", "contains_all": [prefix], "case_sensitive": False},
        ],
    )


def _sql_union_results(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Union High and Low Scores",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL query that uses UNION to combine two SELECT statements from "
            f"{prefix}_results(student_id, score). "
            "First SELECT gets scores >= 70 ('High'). Second SELECT gets scores < 40 ('Needs Review'). "
            "Include a source label in each SELECT."
        ),
        starter_code=(
            f"SELECT student_id, score, 'High' AS source FROM {prefix}_results WHERE score >= 70\n"
            f"UNION\n"
            f"SELECT ;"
        ),
        expected_output="Combined list of high and low scoring students with a source label.",
        solution_notes="Use UNION (deduplicates) or UNION ALL. Both SELECTs must have same number of columns.",
        checks=[
            {"label": "Uses UNION", "contains_all": ["union"], "case_sensitive": False},
            {"label": "Filters high scores", "contains_all": ["score", "70"], "case_sensitive": False},
            {"label": "Filters low scores", "contains_all": ["score", "40"], "case_sensitive": False},
        ],
    )


def _sql_exists_check(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: EXISTS Subquery Check",
        practical_type="database",
        difficulty="advanced",
        prompt=(
            f"Write an SQL query for {prefix}_students(student_id, full_name). "
            "Return student_id and full_name for students who have at least one submission "
            f"in {prefix}_submissions(student_id, score). Use EXISTS."
        ),
        starter_code=(
            f"SELECT student_id, full_name\nFROM {prefix}_students s\n"
            f"WHERE EXISTS (SELECT 1 FROM {prefix}_submissions sub WHERE );"
        ),
        expected_output="Only students with at least one submission are listed.",
        solution_notes="Use WHERE EXISTS with a correlated subquery matching sub.student_id = s.student_id.",
        checks=[
            {"label": "Uses EXISTS", "contains_all": ["exists"], "case_sensitive": False},
            {"label": "Correlated subquery", "contains_all": ["student_id"], "case_sensitive": False},
            {"label": "Selects required fields", "contains_all": ["full_name"], "case_sensitive": False},
        ],
    )


def _sql_date_group(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: Group Submissions by Month",
        practical_type="database",
        difficulty="intermediate",
        prompt=(
            f"Write an SQL query for {prefix}_submissions(student_id, score, submitted_at). "
            "Return the year, month, and number of submissions for each month. "
            "Order by year descending, month ascending."
        ),
        starter_code=(
            f"SELECT EXTRACT(YEAR FROM submitted_at) AS year, EXTRACT(MONTH FROM submitted_at) AS month, \n"
            f"FROM {prefix}_submissions\n"
            f"GROUP BY \n"
            f"ORDER BY year DESC, month ASC;"
        ),
        expected_output="Monthly submission counts ordered chronologically.",
        solution_notes="Use EXTRACT to get year/month parts, COUNT(*), and GROUP BY both extracted fields.",
        checks=[
            {"label": "Extracts date parts", "contains_all": ["extract", "year", "month"], "case_sensitive": False},
            {"label": "Uses GROUP BY", "contains_all": ["group by"], "case_sensitive": False},
            {"label": "Orders results", "contains_all": ["order by"], "case_sensitive": False},
        ],
    )


def _sql_alter_add(course: Course, seed: int) -> dict:
    prefix = _sql_slug(course.code)
    return _spec(
        title="Database: ALTER TABLE Add Column",
        practical_type="database",
        difficulty="beginner",
        prompt=(
            f"Write an ALTER TABLE statement to add a 'status' column (VARCHAR(30)) "
            f"to the {prefix}_results table with a default value of 'pending'."
        ),
        starter_code=f"ALTER TABLE {prefix}_results\nADD COLUMN ;",
        expected_output="A new status column added to the results table.",
        solution_notes="Use ADD COLUMN with VARCHAR(30) and DEFAULT 'pending'.",
        checks=[
            {"label": "Uses ALTER TABLE", "contains_all": ["alter table"], "case_sensitive": False},
            {"label": "Adds a column", "contains_all": ["add column"], "case_sensitive": False},
            {"label": "Sets default", "contains_all": ["default", "pending"], "case_sensitive": False},
        ],
    )


def _stable_int(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _choice(values: list[int], seed: int) -> int:
    return values[seed % len(values)]


def _code_suffix(seed: int) -> str:
    return hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:5]


def _java_suffix(seed: int) -> str:
    return "D" + hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:5].upper()


def _difficulty(seed: int) -> str:
    return ["beginner", "intermediate", "advanced"][seed % 3]


def _sql_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "course"


def _utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)
