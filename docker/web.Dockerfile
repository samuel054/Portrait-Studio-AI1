FROM node:22-alpine

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /workspace/frontend

COPY frontend/package.json ./package.json
RUN npm install

COPY frontend .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]
