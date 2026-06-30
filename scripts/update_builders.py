"""Script to add execution run checks to builder functions in practical_schedule.py"""
import re

with open("app/practical_schedule.py", encoding="utf-8") as f:
    content = f.read()

# Python builder run check mappings: (function_name, test_args_call, expected_return, expected_display)
PY_RUN_TESTS = {
    "_python_count_scores": ('fn([42, {threshold}, {threshold + 8}])', "2", "2"),
    "_python_average_minutes": ('fn([{sample}, {sample + 5}, {sample + 10}])', "{sample + 5}", "avg"),
    "_python_format_course": ("fn('{code}', '{title}')", None, "LABEL"),
    "_python_topic_counts": ("fn(['SQL', 'SQL', 'Python'])", None, "DICT"),
    "_python_linear_search": ("fn(['Amina', 'Bala', 'Chidi'], 'Bala')", "1", "1"),
    "_python_top_scores": ("fn([55, 90, 72, 88])", None, "LIST"),
    "_python_palindrome": ("fn('Racecar')", "True", "True"),
    "_python_reverse_string": ("fn('hello')", "olleh", "olleh"),
    "_python_two_sum": ("fn([2, 7, 11], {target})", "[0, 1]", "[0, 1]"),
    "_python_fizzbuzz": ("fn(5)", "[1, 2, 'Fizz', 4, 'Buzz']", "FIZZBUZZ"),
    "_python_count_vowels": ("fn('OpenED')", "3", "3"),
    "_python_even_numbers": ("fn([1, 2, 3, 4, 5])", "[2, 4]", "[2, 4]"),
    "_python_second_largest": ("fn([10, 20, 30])", "20", "20"),
    "_python_factorial": ("fn(5)", "120", "120"),
    "_python_unique_elements": ("fn([3, 1, 2, 1, 3])", "[3, 1, 2]", "[3, 1, 2]"),
    "_python_positive_count": ("fn([-5, 0, 3, 8, -1])", "2", "2"),
    "_python_anagram_check": ("fn('Listen', 'Silent')", "True", "True"),
    "_python_max_in_list": ("fn([3, 7, 2, 9])", "9", "9"),
    "_python_merge_sorted": ("fn([1, 3, 5], [2, 4, 6])", "[1, 2, 3, 4, 5, 6]", "MERGED"),
    "_python_count_words": ("fn('Hello world')", "2", "2"),
}

# Hardcode replacements for simpler cases
PY_REPLACE = {
    "_python_count_scores": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses the score threshold", "contains_any": [f">= {threshold}", f">={threshold}"]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([42, {threshold}, {threshold + 8}]))", "expected_output": "2"},
        ],""",
    "_python_average_minutes": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Handles empty lists", "contains_all": ["0"]},
            {"label": "Calculates an average", "contains_all": ["sum", "len"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([{sample}, {sample + 5}, {sample + 10}]))", "expected_output": str(int({sample + 5}))},
        ],""",
    "_python_format_course": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uppercases the code", "contains_all": [".upper("]},
            {"label": "Returns a label", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('{course.code.lower()}', '{course.title}'))", "expected_output": f"'{course.code} - {course.title}'"},
        ],""",
    "_python_topic_counts": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a dictionary", "contains_any": ["{}", "dict("]},
            {"label": "Loops and returns counts", "contains_all": ["for ", "return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(['SQL', 'SQL', 'Python']))", "expected_output": str({{'SQL': 2, 'Python': 1}}).replace(' ', '')},
        ],""",
    "_python_linear_search": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Searches with a loop", "contains_any": ["for ", "while "]},
            {"label": "Handles missing values", "contains_all": ["-1"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(['Amina', 'Bala', 'Chidi'], 'Bala'))", "expected_output": "1"},
        ],""",
    "_python_top_scores": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Sorts descending", "contains_any": ["sorted", ".sort("]},
            {"label": "Returns the selected scores", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([55, 90, 72, 88]))", "expected_output": str(sorted([90, 88, 72, 55], reverse=True)[:{limit}]).replace(' ', '')},
        ],""",
    "_python_palindrome": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Ignores case", "contains_all": [".lower("]},
            {"label": "Compares reversed string", "contains_any": ["[::-1]", "reversed("]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('Racecar'))", "expected_output": "True"},
        ],""",
    "_python_reverse_string": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a loop", "contains_any": ["for ", "while "]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('hello'))", "expected_output": "olleh"},
        ],""",
    "_python_two_sum": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a dictionary", "contains_any": ["{}", "dict("]},
            {"label": "Returns indices", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([2, 7, 11], {target}))", "expected_output": str([0, 1])},
        ],""",
    "_python_fizzbuzz": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses modulo operator", "contains_all": ["%"]},
            {"label": "Returns a list", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(5))", "expected_output": str([1, 2, 'Fizz', 4, 'Buzz']).replace(' ', '')},
        ],""",
    "_python_count_vowels": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Ignores case", "contains_all": [".lower("]},
            {"label": "Counts vowels", "contains_any": ["'a'", "'e'", "'i'", "'o'", "'u'", "aeiou"]},
            {"label": "Returns a count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('OpenED'))", "expected_output": "3"},
        ],""",
    "_python_even_numbers": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Checks even numbers", "contains_all": ["%"]},
            {"label": "Returns a list", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([1, 2, 3, 4, 5]))", "expected_output": str([2, 4])},
        ],""",
    "_python_second_largest": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Handles small lists", "contains_all": ["None"]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([10, 20, 30]))", "expected_output": "20"},
        ],""",
    "_python_factorial": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a loop", "contains_any": ["for ", "while "]},
            {"label": "Returns the result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}(5))", "expected_output": "120"},
        ],""",
    "_python_unique_elements": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Uses a set for tracking", "contains_all": ["set("]},
            {"label": "Returns the result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([3, 1, 2, 1, 3]))", "expected_output": str([3, 1, 2]).replace(' ', '')},
        ],""",
    "_python_positive_count": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Compares to zero", "contains_all": ["> 0"]},
            {"label": "Returns a count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([-5, 0, 3, 8, -1]))", "expected_output": "2"},
        ],""",
    "_python_anagram_check": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Ignores case", "contains_all": [".lower("]},
            {"label": "Compares sorted or counted", "contains_any": ["sorted(", "Counter"]},
            {"label": "Returns a result", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('Listen', 'Silent'))", "expected_output": "True"},
        ],""",
    "_python_max_in_list": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Handles empty list", "contains_all": ["None"]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([3, 7, 2, 9]))", "expected_output": "9"},
        ],""",
    "_python_merge_sorted": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Merges without built-in sort", "contains_all": ["return"]},
            {"label": "Handles both lists", "contains_any": ["while ", "for "]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}([1, 3, 5], [2, 4, 6]))", "expected_output": str([1, 2, 3, 4, 5, 6]).replace(' ', '')},
        ],""",
    "_python_count_words": """        checks=[
            {"label": "Defines the required function", "contains_all": [f"def {fn}"]},
            {"label": "Splits the sentence", "contains_all": [".split("]},
            {"label": "Returns a count", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "python", "test_code": f"print({fn}('Hello world'))", "expected_output": "2"},
        ],""",
}

# Java builder run check mappings - test_code is a Main.java file body
JAVA_REPLACE = {
    "_java_count_scores": """        checks=[
            {"label": "Defines the required method", "contains_all": [method, "static", "int[]"]},
            {"label": "Uses the score threshold", "contains_any": [f">= {threshold}", f">={threshold}"]},
            {"label": "Returns a value", "contains_all": ["return"]},
            {"label": "Returns correct result", "run": True, "type": "java", "test_code": "public class Main {\\n    public static void main(String[] args) {\\n        int[] s = {40, " + str({threshold}) + ", " + str({threshold} + 12) + "};\\n        System.out.println(Practice." + method + "(s));\\n    }\\n}", "expected_output": "2"},
        ],""",
}

# For Java builders, the test_code is complex to template. Let me use a different approach:
# post-process the file content to add run checks to Java builders

# Actually, let me just manually edit each one using the edit tool approach.
# Let me write the replacements for Java builders manually.

JAVA_REPLACE = {}

# Java test code templates per builder
java_tests = {
    "_java_count_scores": (method, "2", 'int[] s = {40, ' + str(threshold) + ', ' + str(threshold + 12) + '};\\n        System.out.println(Practice.' + method + '(s));'),
    "_java_average_scores": (method, "75.0", 'int[] s = {60, 75, 90};\\n        System.out.println(Practice.' + method + '(s));'),
    "_java_format_course": (method, "CSC101 - Test", 'System.out.println(Practice.' + method + '("csc101", "Test"));'),
    "_java_find_index": (method, "1", 'String[] s = {"Amina", "Bala"};\\n        System.out.println(Practice.' + method + '(s, "Bala"));'),
    "_java_highest_value": (method, "22", 'int[] v = {14, 22, 9};\\n        System.out.println(Practice.' + method + '(v));'),
    "_java_contains_topic": (method, "true", 'String[] t = {"SQL", "Python"};\\n        System.out.println(Practice.' + method + '(t, "sql"));'),
    "_java_palindrome": (method, "true", 'System.out.println(Practice.' + method + '("Racecar"));'),
    "_java_reverse_string": (method, "olleh", 'System.out.println(Practice.' + method + '("hello"));'),
    "_java_two_sum": (method, "0 1", 'int[] n = {2, 7, 11};\\n        int[] r = Practice.' + method + '(n, 9);\\n        System.out.println(r[0] + " " + r[1]);',
     "expected_output": "0 1"),
    "_java_fizzbuzz": (method, "1 2 Fizz 4 Buzz", 'String[] r = Practice.' + method + '(5);\\n        System.out.println(String.join(" ", r));'),
    "_java_count_vowels": (method, "3", 'System.out.println(Practice.' + method + '("OpenED"));'),
    "_java_even_numbers": (method, "2 4", 'int[] r = Practice.' + method + '(new int[]{1, 2, 3, 4, 5});\\n        System.out.println(r[0] + " " + r[1]);'),
    "_java_second_largest": (method, "20", 'int[] n = {10, 20, 30};\\n        System.out.println(Practice.' + method + '(n));'),
    "_java_factorial": (method, "120", 'System.out.println(Practice.' + method + '(5));'),
    "_java_positive_count": (method, "2", 'int[] n = {-5, 0, 3, 8};\\n        System.out.println(Practice.' + method + '(n));'),
    "_java_anagram_check": (method, "true", 'System.out.println(Practice.' + method + '("Listen", "Silent"));'),
    "_java_max_in_array": (method, "9", 'int[] n = {3, 7, 2, 9};\\n        System.out.println(Practice.' + method + '(n));'),
    "_java_merge_sorted": (method, "1 2 3 4 5 6", 'int[] r = Practice.' + method + '(new int[]{1, 3, 5}, new int[]{2, 4, 6});\\n        System.out.println(Arrays.toString(r));'),
    "_java_count_words": (method, "2", 'System.out.println(Practice.' + method + '("Hello world"));'),
    "_java_fibonacci": (method, "0 1 1 2 3 5", 'int[] r = Practice.' + method + '(6);\\n        for (int v : r) System.out.print(v + " ");'),
}

print("Template written. Edits need to be applied to practical_schedule.py")
