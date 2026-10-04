# Stage 1: Build the static export
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ARG NEXT_PUBLIC_APP_VERSION=dev
ARG NEXT_PUBLIC_GIT_SHA=unknown
ENV NEXT_PUBLIC_APP_VERSION=${NEXT_PUBLIC_APP_VERSION}
ENV NEXT_PUBLIC_GIT_SHA=${NEXT_PUBLIC_GIT_SHA}

# next.config.mjs sets output:'export', so this writes static files to /app/out
RUN npm run build

# Stage 2: Static file server
FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/out ./out/

RUN npm install -g serve

EXPOSE 3000

CMD ["serve", "-s", "out", "-l", "3000"]
