# Stage 1: Build the React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG VITE_APP_VERSION=dev
ARG VITE_GIT_SHA=unknown
ENV VITE_APP_VERSION=${VITE_APP_VERSION}
ENV VITE_GIT_SHA=${VITE_GIT_SHA}

RUN npm run build

# Stage 2: Production runtime - serve static files
FROM node:20-alpine

WORKDIR /app

# Install serve to serve static files
RUN npm install -g serve

COPY --from=builder /app/dist ./dist/

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
