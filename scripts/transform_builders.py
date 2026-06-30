"""Transform practical_schedule.py to add execution run checks to all builders."""
import re

with open("app/practical_schedule.py", encoding="utf-8") as f:
    content = f.read()

# Python builder additions: (builder_name, check_line_to_append)
# Each check_line is inserted as the last item before `],`
PY_ADDITIONS = {
    "_python_count_scores": (),
    "_python_average_minutes": (),
    "_python_format_course": (),
    "_python_topic_counts": (),
    "_python_linear_search": (),
    "_python_top_scores": (),
    "_python_palindrome": (),
    "_python_reverse_string": (),
    "_python_two_sum": (),
    "_python_fizzbuzz": (),
    "_python_count_vowels": (),
    "_python_even_numbers": (),
    "_python_second_largest": (),
    "_python_factorial": (),
    "_python_unique_elements": (),
    "_python_positive_count": (),
    "_python_anagram_check": (),
    "_python_max_in_list": (),
    "_python_merge_sorted": (),
    "_python_count_words": (),
}

# For each Python builder, the last check line varies.
# We'll find the last "return"-related check and add after it.
insertions = {}

# Build replacements: key = function_name, value = (old_last_check, new_last_check + run_check)
replacements = []

# Python builders - add run check after the "return" check
py_replacements = {
    "_python_count_scores": (
        '            {"label": "Returns a result", "contains_all": ["return"]},\n        ],',
        '            {"label": "Returns a result", "contains_all": ["return"]},\n            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([42, {threshold}, {threshold + 8}]))", "expected_output": "2"},\n        ],'
    ),
    "_python_average_minutes": (
        '            {"label": "Calculates an average", "contains_all": ["sum", "len"]},\n        ],',
        '            {"label": "Calculates an average", "contains_all": ["sum", "len"]},\n            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([{sample}, {sample + 5}, {sample + 10}]))", "expected_output": str(int({sample + 5}))},\n        ],'
    ),
}

# Actually, the edit tool approach with these replacements is fragile due to f-string syntax in the file.
# Let me just find each "        ]," that ends a checks list and replace it.
# But that's not unique.

# Best approach: replace the entire `checks=[...],` section for each builder.
# Each builder's checks section is unique because it references the function name.

# Let me construct unique search/replace pairs by reading the actual file content.

# For each Python builder, find its unique checks section start and end
# The pattern is: `checks=[` ... `],` 

# Let me find all `checks=[` in the file and get their surrounding lines
lines = content.split('\n')

# Find all `checks=[` and `],` that end checks blocks
check_blocks = {}  # {func_name: (start_idx, end_idx)}
current_func = None
in_checks = False
check_start = 0

for i, line in enumerate(lines):
    # Detect builder function
    m = re.match(r'^def (_(python|java|sql)_\w+)\(', line)
    if m:
        current_func = m.group(1)
        in_checks = False
    if current_func and 'checks=[' in line:
        check_start = i
        in_checks = True
    if in_checks and line.rstrip().endswith('],') and i > check_start:
        # Check if this is followed by a line that continues the parent or ends the spec
        if i + 1 < len(lines) and not lines[i+1].strip().startswith(('#', 'checks', '"""')):
            pass  # might not be the right closing
        # Check if we're at the end of a checks section inside a spec
        check_blocks[current_func] = (check_start, i)
        in_checks = False

# Print found blocks for debugging
for func, (s, e) in check_blocks.items():
    if func not in ('_spec', '_stable_int', '_choice', '_code_suffix', '_java_suffix', '_difficulty', '_sql_slug', '_utc_naive'):
        print(f"{func}: lines {s+1}-{e+1}")
        if e - s <= 15:
            for j in range(s, e+1):
                print(f"  {j+1}: {lines[j]}")
        print()
