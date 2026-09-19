# Previously ran `npm run dev` (Vite's dev server) directly in the
# container this whole app is meant to be judged/demoed through. That
# meant: no minification, unnecessary HMR-websocket overhead, and —
# the real risk for a demo — Vite's dev-mode error overlay (a full-screen
# red panel) would cover the entire app on any runtime JS error instead
# of failing gracefully. This app was already being built once and run
# as a fixed artifact in practice (docker-compose.yml never mounted a
# live volume for this service, unlike backend's), so a real production
# build is more consistent with the existing setup, not a departure
# from it.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# Vite bakes import.meta.env.VITE_* values in at BUILD time, not container
# runtime -- docker-compose's `env_file`/`environment` only reach a running
# container, never the `docker build` step. Without this ARG threaded
# through from docker-compose.yml's build.args, VITE_API_BASE_URL would be
# silently ignored during the build no matter what .env says, falling back
# to the hardcoded default below with no error or warning.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
