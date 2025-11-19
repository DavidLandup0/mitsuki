FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY app.js .

EXPOSE 8000

CMD ["node", "app.js"]
