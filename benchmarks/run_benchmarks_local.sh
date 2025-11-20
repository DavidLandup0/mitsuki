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

# Cleanup function
cleanup() {
  echo "Cleaning up processes..."
  if [ ! -z "$CURRENT_PID" ]; then
    if ps -p $CURRENT_PID > /dev/null 2>&1; then
      kill $CURRENT_PID 2>/dev/null || true
      wait $CURRENT_PID 2>/dev/null || true
    fi
  fi
}

trap cleanup EXIT

# Benchmark Mitsuki-Socketify
echo "----------------------------------------"
echo "Benchmarking mitsuki-socketify on port 8000"
echo "----------------------------------------"
cd mitsuki-socketify
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/mitsuki-socketify-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Mitsuki-Granian
echo "----------------------------------------"
echo "Benchmarking mitsuki-granian on port 8000"
echo "----------------------------------------"
cd mitsuki-granian
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/mitsuki-granian-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Mitsuki-Uvicorn
echo "----------------------------------------"
echo "Benchmarking mitsuki-uvicorn on port 8000"
echo "----------------------------------------"
cd mitsuki-uvicorn
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/mitsuki-uvicorn-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark FastAPI
echo "----------------------------------------"
echo "Benchmarking fastapi on port 8000"
echo "----------------------------------------"
cd fastapi
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/fastapi-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Starlette-Uvicorn
echo "----------------------------------------"
echo "Benchmarking starlette-uvicorn on port 8000"
echo "----------------------------------------"
cd starlette-uvicorn
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/starlette-uvicorn-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Starlette-Granian
echo "----------------------------------------"
echo "Benchmarking starlette-granian on port 8000"
echo "----------------------------------------"
cd starlette-granian
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/starlette-granian-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Flask
echo "----------------------------------------"
echo "Benchmarking flask on port 8000"
echo "----------------------------------------"
cd flask
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/flask-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Django
echo "----------------------------------------"
echo "Benchmarking django on port 8000"
echo "----------------------------------------"
cd django
python3 app.py &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/django-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Elysia
echo "----------------------------------------"
echo "Benchmarking elysia on port 8000"
echo "----------------------------------------"
cd elysia
bun app.ts &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/elysia-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Benchmark Express
echo "----------------------------------------"
echo "Benchmarking express on port 8000"
echo "----------------------------------------"
cd express
node app.js &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/express-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

# Spring Boot - need to build first
echo "----------------------------------------"
echo "Benchmarking spring on port 8000"
echo "----------------------------------------"
cd spring_boot
if [ ! -f target/*.jar ]; then
  echo "Building Spring Boot application..."
  mvn package -DskipTests
fi
java -jar target/*.jar &
CURRENT_PID=$!
cd ..
wait_for_service 8000
echo "Warming up..."
wrk -t4 -c100 -d5s http://0.0.0.0:8000 > /dev/null 2>&1
echo "Running benchmark..."
wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/spring-local.txt
kill $CURRENT_PID
wait $CURRENT_PID 2>/dev/null || true
CURRENT_PID=""
sleep 2

echo "Benchmarks finished. Results are in the 'results' directory."
