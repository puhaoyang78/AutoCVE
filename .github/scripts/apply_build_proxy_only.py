from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


compose = Path("docker-compose.yml")
text = compose.read_text(encoding="utf-8")
old_args = '''      args:\n        http_proxy: ''\n        https_proxy: ''\n        HTTP_PROXY: ''\n        HTTPS_PROXY: ''\n        all_proxy: ''\n        ALL_PROXY: ''\n'''
new_args = '''      args:\n        HTTP_PROXY: ${HTTP_PROXY:-}\n        HTTPS_PROXY: ${HTTPS_PROXY:-}\n        http_proxy: ${HTTP_PROXY:-}\n        https_proxy: ${HTTPS_PROXY:-}\n        NO_PROXY: ${NO_PROXY:-localhost,127.0.0.1}\n        no_proxy: ${NO_PROXY:-localhost,127.0.0.1}\n      extra_hosts:\n        - "host.docker.internal:host-gateway"\n'''
if text.count(old_args) != 2:
    raise RuntimeError(f"docker-compose.yml: expected two backend/frontend build arg blocks, found {text.count(old_args)}")
text = text.replace(old_args, new_args)

# Frontend already has Vite build args after the old proxy block. Keep them inside
# build.args, before build.extra_hosts.
text = text.replace(
    '''      extra_hosts:\n        - "host.docker.internal:host-gateway"\n        VITE_ENABLE_CHECKMARX_SCAN: ${VITE_ENABLE_CHECKMARX_SCAN:-false}\n        VITE_APP_VERSION: ${VITE_APP_VERSION:-}\n''',
    '''        VITE_ENABLE_CHECKMARX_SCAN: ${VITE_ENABLE_CHECKMARX_SCAN:-false}\n        VITE_APP_VERSION: ${VITE_APP_VERSION:-}\n      extra_hosts:\n        - "host.docker.internal:host-gateway"\n''',
    1,
)

old_runtime_proxy = '''      HTTP_PROXY: ''\n      HTTPS_PROXY: ''\n      http_proxy: ''\n      https_proxy: ''\n      NO_PROXY: '*'\n'''
if text.count(old_runtime_proxy) != 4:
    raise RuntimeError(f"docker-compose.yml: expected four runtime proxy blocks, found {text.count(old_runtime_proxy)}")
text = text.replace(old_runtime_proxy, "")

old_sandbox = '''  sandbox:\n    build:\n      context: ./docker/sandbox\n      args:\n        PIP_INDEX_URL: ${SANDBOX_PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}\n'''
new_sandbox = '''  sandbox:\n    build:\n      context: ./docker/sandbox\n      args:\n        HTTP_PROXY: ${HTTP_PROXY:-}\n        HTTPS_PROXY: ${HTTPS_PROXY:-}\n        http_proxy: ${HTTP_PROXY:-}\n        https_proxy: ${HTTPS_PROXY:-}\n        NO_PROXY: ${NO_PROXY:-localhost,127.0.0.1}\n        no_proxy: ${NO_PROXY:-localhost,127.0.0.1}\n        PIP_INDEX_URL: ${SANDBOX_PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}\n      extra_hosts:\n        - "host.docker.internal:host-gateway"\n'''
if old_sandbox not in text:
    raise RuntimeError("sandbox build block not found")
text = text.replace(old_sandbox, new_sandbox, 1)
compose.write_text(text, encoding="utf-8")

path = "backend/Dockerfile"
text = Path(path).read_text(encoding="utf-8")
old_builder_env = '''ENV PYTHONDONTWRITEBYTECODE=1\nENV PYTHONUNBUFFERED=1\nENV http_proxy=""\nENV https_proxy=""\nENV HTTP_PROXY=""\nENV HTTPS_PROXY=""\nENV all_proxy=""\nENV ALL_PROXY=""\nENV no_proxy="*"\nENV NO_PROXY="*"\nENV PIP_INDEX_URL=https://pypi.org/simple\n'''
new_builder_env = '''ENV PYTHONDONTWRITEBYTECODE=1\nENV PYTHONUNBUFFERED=1\nARG HTTP_PROXY\nARG HTTPS_PROXY\nARG http_proxy\nARG https_proxy\nARG NO_PROXY\nARG no_proxy\nENV PIP_INDEX_URL=https://pypi.org/simple\n'''
if old_builder_env not in text:
    raise RuntimeError("backend builder proxy env block not found")
text = text.replace(old_builder_env, new_builder_env, 1)

old_runtime_env = '''ENV PYTHONDONTWRITEBYTECODE=1\nENV PYTHONUNBUFFERED=1\nENV http_proxy=""\nENV https_proxy=""\nENV HTTP_PROXY=""\nENV HTTPS_PROXY=""\nENV all_proxy=""\nENV ALL_PROXY=""\nENV no_proxy="*"\nENV NO_PROXY="*"\n'''
new_runtime_env = '''ENV PYTHONDONTWRITEBYTECODE=1\nENV PYTHONUNBUFFERED=1\nARG HTTP_PROXY\nARG HTTPS_PROXY\nARG http_proxy\nARG https_proxy\nARG NO_PROXY\nARG no_proxy\n'''
if old_runtime_env not in text:
    raise RuntimeError("backend runtime-stage proxy env block not found")
text = text.replace(old_runtime_env, new_runtime_env, 1)

text = text.replace(
    '''RUN rm -f /etc/apt/apt.conf.d/proxy.conf 2>/dev/null || true     && echo 'Acquire::http::Proxy "false";' > /etc/apt/apt.conf.d/99-no-proxy     && echo 'Acquire::https::Proxy "false";' >> /etc/apt/apt.conf.d/99-no-proxy     && echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99-no-proxy     && echo 'Acquire::http::Timeout "30";' >> /etc/apt/apt.conf.d/99-no-proxy     && echo 'Acquire::https::Timeout "30";' >> /etc/apt/apt.conf.d/99-no-proxy     && apt-get update''',
    '''RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99-retries     && echo 'Acquire::http::Timeout "30";' >> /etc/apt/apt.conf.d/99-retries     && echo 'Acquire::https::Timeout "30";' >> /etc/apt/apt.conf.d/99-retries     && apt-get update'''
)
if 'Proxy "false"' in text or 'ENV HTTP_PROXY=""' in text:
    raise RuntimeError("backend Dockerfile still forces proxy bypass")
Path(path).write_text(text, encoding="utf-8")

path = "frontend/Dockerfile"
text = Path(path).read_text(encoding="utf-8")
old_frontend_proxy = '''# 彻底清除代理设置\nENV http_proxy=""\nENV https_proxy=""\nENV HTTP_PROXY=""\nENV HTTPS_PROXY=""\nENV all_proxy=""\nENV ALL_PROXY=""\nENV no_proxy="*"\nENV NO_PROXY="*"\n'''
new_frontend_proxy = '''# 代理仅用于镜像构建，不写入最终 Nginx 运行镜像。\nARG HTTP_PROXY\nARG HTTPS_PROXY\nARG http_proxy\nARG https_proxy\nARG NO_PROXY\nARG no_proxy\n'''
if old_frontend_proxy not in text:
    raise RuntimeError("frontend proxy block not found")
text = text.replace(old_frontend_proxy, new_frontend_proxy, 1)
Path(path).write_text(text, encoding="utf-8")

path = "docker/sandbox/Dockerfile"
text = Path(path).read_text(encoding="utf-8")
needle = '''ARG SEMGREP_VERSION=1.161.0\nARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/\n'''
replacement = '''ARG SEMGREP_VERSION=1.161.0\nARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/\nARG HTTP_PROXY\nARG HTTPS_PROXY\nARG http_proxy\nARG https_proxy\nARG NO_PROXY\nARG no_proxy\n'''
if needle not in text:
    raise RuntimeError("sandbox ARG marker not found")
text = text.replace(needle, replacement, 1)
text = text.replace('RUN unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY && \\\n', 'RUN ')
if 'unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY' in text:
    raise RuntimeError("sandbox Dockerfile still clears proxy")
Path(path).write_text(text, encoding="utf-8")
