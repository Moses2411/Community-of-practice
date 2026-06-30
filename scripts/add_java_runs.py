"""Add run checks to Java builders in practical_schedule.py."""
import re

with open("app/practical_schedule.py", encoding="utf-8") as f:
    content = f.read()

# For each Java builder, we need to add a run check after the last check line
# The replacement pattern: find `],` after a builder's checks and add a new check before it

# Java test data: (expected_output, java_main_body_with_placeholder_METHOD_)
# We'll use METHOD_ as placeholder and replace with the actual method variable name
java_tests = {
    "_java_count_scores": ("2", 'int[] s = {40, THRESH_, THRESH2_};\\n        System.out.println(Practice.METHOD_(s));'),
    "_java_average_scores": ("75.0", 'int[] s = {60, 75, 90};\\n        System.out.println(Practice.METHOD_(s));'),
    "_java_format_course": ("CSC101 - Test", 'System.out.println(Practice.METHOD_("csc101", "Test"));'),
    "_java_find_index": ("1", 'String[] s = {"Amina", "Bala"};\\n        System.out.println(Practice.METHOD_(s, "Bala"));'),
    "_java_highest_value": ("22", 'int[] v = {14, 22, 9};\\n        System.out.println(Practice.METHOD_(v));'),
    "_java_contains_topic": ("true", 'String[] t = {"SQL", "Python"};\\n        System.out.println(Practice.METHOD_(t, "sql"));'),
    "_java_palindrome": ("true", 'System.out.println(Practice.METHOD_("Racecar"));'),
    "_java_reverse_string": ("olleh", 'System.out.println(Practice.METHOD_("hello"));'),
    "_java_two_sum": ("0 1", 'int[] n = {2, 7, 11};\\n        int[] r = Practice.METHOD_(n, 9);\\n        System.out.println(r[0] + " " + r[1]);'),
    "_java_fizzbuzz": ("1 2 Fizz 4 Buzz", 'String[] r = Practice.METHOD_(5);\\n        for (String v : r) System.out.print(v + " ");'),
    "_java_count_vowels": ("3", 'System.out.println(Practice.METHOD_("OpenED"));'),
    "_java_even_numbers": ("2 4", 'int[] r = Practice.METHOD_(new int[]{1, 2, 3, 4, 5});\\n        System.out.println(r[0] + " " + r[1]);'),
    "_java_second_largest": ("20", 'int[] n = {10, 20, 30};\\n        System.out.println(Practice.METHOD_(n));'),
    "_java_factorial": ("120", 'System.out.println(Practice.METHOD_(5));'),
    "_java_positive_count": ("2", 'int[] n = {-5, 0, 3, 8};\\n        System.out.println(Practice.METHOD_(n));'),
    "_java_anagram_check": ("true", 'System.out.println(Practice.METHOD_("Listen", "Silent"));'),
    "_java_max_in_array": ("9", 'int[] n = {3, 7, 2, 9};\\n        System.out.println(Practice.METHOD_(n));'),
    "_java_merge_sorted": ("1 2 3 4 5 6", 'int[] r = Practice.METHOD_(new int[]{1, 3, 5}, new int[]{2, 4, 6});\\n        for (int v : r) System.out.print(v + " ");'),
    "_java_count_words": ("2", 'System.out.println(Practice.METHOD_("Hello world"));'),
    "_java_fibonacci": ("0 1 1 2 3 5", 'int[] r = Practice.METHOD_(6);\\n        for (int v : r) System.out.print(v + " ");'),
}

def make_java_check(method_name, expected_output, main_body):
    body = main_body.replace("METHOD_", method_name)
    test_code = f"public class Main {{\\n    public static void main(String[] args) {{\\n        {body}\\n    }}\\n}}"
    return f'{{"label": "Returns correct result", "run": True, "type": "java", "test_code": "{test_code}", "expected_output": "{expected_output}"}}'

# Process each Java builder
for func_name in java_tests:
    exp, body_tmpl = java_tests[func_name]
    
    if func_name == "_java_count_scores":
        # Special case: threshold varies
        continue  # skip for now, handle manually
    
    # Find the function definition to get the method variable name
    # The pattern is: method = f"..." or method = "..."
    func_match = re.search(rf'def {func_name}\(.*?\):(.*?)(?=def |\Z)', content, re.DOTALL)
    if not func_match:
        print(f"WARNING: Could not find {func_name}")
        continue
    
    func_body = func_match.group(1)
    method_match = re.search(r'method\s*=\s*(?:f)?["\'](\w+)', func_body)
    if not method_match:
        print(f"WARNING: Could not find method variable in {func_name}")
        continue
    
    method_name = method_match.group(1)
    
    # Find the checks section end: `],` that ends checks
    checks_match = re.search(r'checks=\[(.*?)\],\n', func_body, re.DOTALL)
    if not checks_match:
        print(f"WARNING: Could not find checks in {func_name}")
        continue
    
    checks_end = checks_match.group(0)
    
    # Replace the last check + `],` with last check + new check + `],`
    run_check = make_java_check(method_name, exp, body_tmpl)
    
    # Find the old pattern: if method_name contains f-string variables, we need to handle it
    # Actually the method variable in the checks is literally {method} in an f-string
    # So we need to make the new check with the Python f-string syntax
    
    # Let's use a different approach - find the last actual check line
    lines = func_body.split('\n')
    last_check_line_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if '{"label":' in lines[i]:
            last_check_line_idx = i
            break
    
    if last_check_line_idx is None:
        print(f"WARNING: Could not find last check in {func_name}")
        continue
    
    # Create the new check with proper f-string handling
    # The existing checks use `{method}` in f-strings
    # We need our new check to also use `{method}` for Java test_code
    
    # Build the check dict as Python code
    java_class = r'"public class Main {{\n    public static void main(String[] args) {{\n'
    java_body = body_tmpl.replace("METHOD_", "{method}")
    java_end = r'\n    }}\n}}"'
    
    run_check_line = f'            {{"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\\n    public static void main(String[] args) {{\\n        {java_body}\\n    }}\\n}}", "expected_output": "{exp}"}},'
    
    # Find the actual old content to replace
    old_lines = content.split('\n')
    
    # Find the function start
    func_start = None
    for i, line in enumerate(old_lines):
        if line.startswith(f'def {func_name}('):
            func_start = i
            break
    
    if func_start is None:
        print(f"WARNING: Could not find function start for {func_name}")
        continue
    
    # Find checks section within the function
    in_func_checks = False
    check_end_line = None
    for i in range(func_start, min(func_start + 60, len(old_lines))):
        line = old_lines[i]
        if 'checks=[' in line:
            in_func_checks = True
        if in_func_checks and line.rstrip().endswith('],') and i > func_start + 5:
            check_end_line = i
            break
    
    if check_end_line is None:
        print(f"WARNING: Could not find checks end for {func_name}")
        continue
    
    # The old last check is the line before check_end_line
    old_last_line = old_lines[check_end_line - 1]
    
    # Check if run check already exists
    if 'Returns correct result' in content:
        # Check if this builder already has it
        func_content = '\n'.join(old_lines[func_start:check_end_line+1])
        if '"Returns correct result"' in func_content and '"run": True' in func_content:
            print(f"SKIP {func_name}: run check already exists")
            continue
    
    # Build the run check line
    # Escape properly for the f-string inside Python
    body_escaped = java_body
    
    run_line = f'            {{"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {{\\n    public static void main(String[] args) {{\\n        {body_escaped}\\n    }}\\n}}", "expected_output": "{exp}"}},'
    
    # Replace: add the run check before `],`
    old_text = old_lines[check_end_line - 1] + '\n        ],'
    # We need to find the exact 12 spaces before `],`
    spacing = '        '
    
    # For _java_count_scores, the threshold varies so it's more complex
    if func_name == "_java_count_scores":
        print(f"SKIP {func_name}: has dynamic threshold, needs manual edit")
        continue
    
    # Do the replacement
    new_text = old_lines[check_end_line - 1] + '\n' + run_line + '\n        ],'
    old_text = old_lines[check_end_line - 1] + '\n        ],'
    
    if old_text in content:
        content = content.replace(old_text, new_text, 1)
        print(f"OK {func_name}: added run check")
    else:
        print(f"FAIL {func_name}: could not find old_text")
        # Debug: show what we're looking for
        print(f"  Looking for: {repr(old_text[:80])}")

# Handle _java_count_scores specially
func_name = "_java_count_scores"
# Find the function
lines = content.split('\n')
func_start = None
for i, line in enumerate(lines):
    if line.startswith(f'def {func_name}('):
        func_start = i
        break

if func_start:
    for i in range(func_start, min(func_start + 60, len(lines))):
        if lines[i].rstrip().endswith('],') and i > func_start + 5:
            check_end_line = i
            break
    
    old_last = lines[check_end_line - 1]
    # Java count_scores: threshold varies, use dynamic f-string
    run_line = '            {"label": "Returns correct result", "run": True, "type": "java", "test_code": f"public class Main {\\n    public static void main(String[] args) {\\n        int[] s = {{{40, {threshold}, {threshold + 12}}}};\\n        System.out.println(Practice.{method}(s));\\n    }\\n}", "expected_output": "2"},'
    
    old_text = old_last + '\n        ],'
    new_text = old_last + '\n' + run_line + '\n        ],'
    if old_text in content:
        content = content.replace(old_text, new_text, 1)
        print(f"OK {func_name}: added run check")
    else:
        print(f"FAIL {func_name}")

with open("app/practical_schedule.py", "w", encoding="utf-8") as f:
    f.write(content)

print("\nDone!")
