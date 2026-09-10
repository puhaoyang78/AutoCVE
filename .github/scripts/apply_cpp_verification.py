from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "backend/app/services/agent/tools/run_code.py"

replace_once(path, "import asyncio\n", "import asyncio\nimport base64\n")

text = Path(path).read_text(encoding="utf-8")
old_languages = "python, php, javascript, ruby, go, java, bash"
count = text.count(old_languages)
if count < 3:
    raise RuntimeError(f"{path}: expected repeated language list, found {count}")
Path(path).write_text(
    text.replace(old_languages, "python, php, javascript, ruby, go, java, c, cpp, bash"),
    encoding="utf-8",
)

replace_once(
    path,
    "- java: javac + java (需写完整 class)\n- bash: bash -c 'code'\n",
    "- java: javac + java (需写完整 class)\n- c: gcc + ASan/UBSan (需写完整 main)\n- cpp/c++: g++ + ASan/UBSan (需写完整 main)\n- bash: bash -c 'code'\n",
)

cpp_branch = '''        elif language in ["c", "cpp", "c++"]:\n            suffix = "c" if language == "c" else "cpp"\n            compiler = "gcc" if language == "c" else "g++"\n            standard = "-std=c11" if language == "c" else "-std=c++17"\n            encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")\n            sanitizer_flags = "-fsanitize=address,undefined -fno-omit-frame-pointer -O1 -g"\n            return (\n                f"printf '%s' '{encoded}' | base64 -d > /tmp/main.{suffix} && "\n                f"{compiler} {standard} {sanitizer_flags} /tmp/main.{suffix} -o /tmp/autocve_test && "\n                "ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=print_stacktrace=1 /tmp/autocve_test"\n            )\n\n'''

replace_once(path, '        elif language == "go":\n', cpp_branch + '        elif language == "go":\n')

replace_once(
    "backend/app/services/agent/agents/verification.py",
    "**run_code**: 执行你编写的测试代码（支持 Python/PHP/JS/Ruby/Go/Java/Bash）",
    "**run_code**: 执行你编写的测试代码（支持 Python/PHP/JS/Ruby/Go/Java/C/C++/Bash）",
)

test_path = Path("backend/tests/services/test_run_code_cpp.py")
test_path.parent.mkdir(parents=True, exist_ok=True)
test_path.write_text(
    '''import subprocess\n\nfrom app.services.agent.tools.run_code import RunCodeTool\n\n\ndef test_c_command_uses_gcc_and_sanitizers():\n    command = RunCodeTool()._build_command("int main(void) { return 0; }", "c")\n    assert command is not None\n    assert "gcc -std=c11" in command\n    assert "-fsanitize=address,undefined" in command\n    assert "/tmp/main.c" in command\n\n\ndef test_cpp_command_uses_gpp_and_sanitizers():\n    command = RunCodeTool()._build_command("int main() { return 0; }", "cpp")\n    assert command is not None\n    assert "g++ -std=c++17" in command\n    assert "-fsanitize=address,undefined" in command\n    assert "/tmp/main.cpp" in command\n\n\ndef test_cpp_alias_matches_cpp_command():\n    tool = RunCodeTool()\n    code = "int main() { return 0; }"\n    assert tool._build_command(code, "c++") == tool._build_command(code, "cpp")\n\n\ndef test_generated_c_command_compiles_and_runs():\n    command = RunCodeTool()._build_command("int main(void) { return 0; }", "c")\n    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)\n    assert result.returncode == 0, result.stderr\n\n\ndef test_asan_reports_memory_error():\n    code = "#include <stdlib.h>\\nint main(void) { int *p = malloc(sizeof(int)); free(p); return *p; }"\n    command = RunCodeTool()._build_command(code, "c")\n    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)\n    assert result.returncode != 0\n    assert "AddressSanitizer" in result.stderr or "runtime error" in result.stderr\n''',
    encoding="utf-8",
)
