#!/bin/bash
set -e

# Function to wait for a service to be ready
wait_for_service() {
  local port=$1
  echo "Waiting for service on port $port to be ready..."
  until $(curl --output /dev/null --silent --fail http://127.0.0.1:$port); do
    printf '.'
    sleep 1
  done
  echo "Service on port $port is ready."
}

# Create results directory
mkdir -p results

# Define services and their ports
services=("mitsuki-socketify" "mitsuki-granian" "mitsuki-uvicorn" "fastapi" "starlette-uvicorn" "starlette-granian" "flask" "django" "elysia" "spring" "express")

# Run benchmarks for each service in isolation
for i in ${!services[@]}; do
  service=${services[$i]}
  port=8000
  echo "----------------------------------------"
  echo "Benchmarking $service on port $port"
  echo "----------------------------------------"

  # Start the service
  echo "Starting $service..."
  # Use legacy builder for mitsuki-socketify to avoid QEMU emulation issues
  if [ "$service" = "mitsuki-socketify" ]; then
    DOCKER_BUILDKIT=0 docker-compose up -d --build $service
  else
    docker-compose up -d --build $service
  fi

  # Wait for the service to be ready
  wait_for_service $port

  # Run the benchmark
  echo "Warming up..."
  wrk -t4 -c100 -d5s http://127.0.0.1:$port > /dev/null 2>&1
  echo "Running benchmark..."
  wrk -t4 -c100 -d30s http://127.0.0.1:$port > results/$service.txt

  # Stop the service
  echo "Stopping $service..."
  docker-compose down
done

echo "Benchmarks finished. Results are in the 'results' directory."
