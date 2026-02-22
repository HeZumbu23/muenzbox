# Build stage
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
ARG VITE_BUILD_NUMBER=dev
ARG VITE_COMMIT_MSG=local
ENV VITE_BUILD_NUMBER=$VITE_BUILD_NUMBER
ENV VITE_COMMIT_MSG=$VITE_COMMIT_MSG
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8421
CMD ["nginx", "-g", "daemon off;"]
