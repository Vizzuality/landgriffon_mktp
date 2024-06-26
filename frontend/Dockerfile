# Use an official Node.js runtime as a parent image
FROM node:21.5.0-alpine
WORKDIR /app
COPY app/package.json app/package-lock.json ./
RUN npm install
COPY app ./
RUN npm run build
RUN npm install -g serve
EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
