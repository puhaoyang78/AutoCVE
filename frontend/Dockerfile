# =============================================
# AutoCVE Frontend Docker 构建
# =============================================
# 使用 Nginx 提供静态文件和反向代理 (支持 SSE 流式传输)

FROM node:20-slim AS builder

WORKDIR /app

ARG VITE_ENABLE_CHECKMARX_SCAN=false
ARG VITE_APP_VERSION

# 代理仅用于镜像构建，不写入最终 Nginx 运行镜像。
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
ARG NO_PROXY
ARG no_proxy

# 锁定 pnpm 9，与 lockfileVersion 9.0 保持一致。
RUN npm config set registry https://registry.npmmirror.com && \
    npm install -g pnpm@9 && \
    pnpm config set registry https://registry.npmmirror.com

# 复制依赖文件
COPY package.json pnpm-lock.yaml ./

# 网络重试/超时作为 install 参数传入，避免写入新版 pnpm 不支持的全局配置键。
RUN pnpm install --frozen-lockfile \
    --network-concurrency 1 \
    --fetch-retries 5 \
    --fetch-timeout 300000

# 复制源码
COPY . .

# 🔥 构建时使用占位符 - 实现 Build Once Run Anywhere
ENV VITE_API_BASE_URL=__API_BASE_URL__
ENV VITE_ENABLE_CHECKMARX_SCAN=${VITE_ENABLE_CHECKMARX_SCAN}
ENV VITE_APP_VERSION=${VITE_APP_VERSION}

# 构建生产版本
RUN pnpm build

# =============================================
# 生产镜像 - 使用 Nginx (支持 SSE 反向代理)
# =============================================
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置 (包含 SSE 反向代理配置)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制启动脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
