import subprocess

from app.services.agent.tools.run_code import RunCodeTool


def test_c_command_uses_gcc_and_sanitizers():
    command = RunCodeTool()._build_command("int main(void) { return 0; }", "c")
    assert command is not None
    assert "gcc -std=c11" in command
    assert "-fsanitize=address,undefined" in command
    assert "/tmp/main.c" in command


def test_cpp_command_uses_gpp_and_sanitizers():
    command = RunCodeTool()._build_command("int main() { return 0; }", "cpp")
    assert command is not None
    assert "g++ -std=c++17" in command
    assert "-fsanitize=address,undefined" in command
    assert "/tmp/main.cpp" in command


def test_cpp_alias_matches_cpp_command():
    tool = RunCodeTool()
    code = "int main() { return 0; }"
    assert tool._build_command(code, "c++") == tool._build_command(code, "cpp")


def test_generated_c_command_compiles_and_runs():
    command = RunCodeTool()._build_command("int main(void) { return 0; }", "c")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_asan_reports_memory_error():
    code = "#include <stdlib.h>\nint main(void) { int *p = malloc(sizeof(int)); free(p); return *p; }"
    command = RunCodeTool()._build_command(code, "c")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert "AddressSanitizer" in result.stderr or "runtime error" in result.stderr
