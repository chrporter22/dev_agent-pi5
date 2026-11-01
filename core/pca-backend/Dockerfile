# ------------------------------------
# PCA BACKEND — core/pca-backend/Dockerfile
# Build the React bundle with Vite, then serve dist/ + proxy /api/*
# to node-api with a small Node http server. No nginx.
# ------------------------------------
FROM node:22-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build

ENV NODE_API_URL=http://node-api:3000
ENV PORT=80

EXPOSE 80

CMD ["node", "serve.mjs"]
