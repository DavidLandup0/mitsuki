# Bun base image
FROM oven/bun:1.0

# Set working directory
WORKDIR /app

# Copy package files and install dependencies
COPY package.json .
COPY bun.lock .
RUN bun install

# Copy benchmark code
COPY app.ts .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["bun", "run", "app.ts"]
