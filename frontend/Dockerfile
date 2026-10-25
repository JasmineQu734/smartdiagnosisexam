FROM node:20-alpine AS build
WORKDIR /app
# 走 npmmirror 镜像源：容器里没有宿主机的 .npmrc，直连官方源会拉不到包
# 锁文件一起拷进来用 npm ci，装出来的依赖与本地构建完全一致（含 three 0.160.0）
COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm ci --no-audit --no-fund
COPY . .
RUN npm run build
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80