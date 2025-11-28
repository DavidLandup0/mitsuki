#!/bin/bash
set -e

# ---------------------------
# Helper: wait for service
# ---------------------------
wait_for_service() {
  local port=$1
  echo "Waiting for service on port $port ..."
  until curl --output /dev/null --silent --fail http://127.0.0.1:$port; do
      printf '.'
      sleep 1
  done
  echo "Service on port $port is ready."
}

# ---------------------------
# Cleanup on exit
# ---------------------------
cleanup() {
  echo "Cleaning up processes..."
  if [ -n "$CURRENT_PID" ] && ps -p "$CURRENT_PID" >/dev/null 2>&1; then
      kill "$CURRENT_PID" 2>/dev/null || true
      wait "$CURRENT_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

mkdir -p results

# ---------------------------
# Framework benchmark function
# ---------------------------
run_benchmark() {
  local name=$1
  local dir=$2
  local start_cmd=$3
  local result_file=$4

  echo "----------------------------------------"
  echo "Benchmarking $name on port 8000"
  echo "----------------------------------------"

  pushd "$dir" >/dev/null
  eval "$start_cmd" &
  CURRENT_PID=$!
  popd >/dev/null

  wait_for_service 8000

  echo "Warming up..."
  wrk -t4 -c100 -d5s  http://0.0.0.0:8000 >/dev/null 2>&1

  echo "Running benchmark..."
  wrk -t4 -c100 -d60s http://0.0.0.0:8000 > "results/$result_file"

  lsof -t -i:8000 | xargs kill
  sleep 2
}

# ---------------------------
# Special Spring Boot function (build first)
# ---------------------------
run_spring_boot() {
  echo "----------------------------------------"
  echo "Benchmarking spring on port 8000"
  echo "----------------------------------------"

  pushd spring_boot >/dev/null
  if ! ls target/*.jar >/dev/null 2>&1; then
    echo "Building Spring Boot application..."
    mvn package -DskipTests
  fi

  java -jar target/*.jar &
  CURRENT_PID=$!

  popd >/dev/null
  wait_for_service 8000

  echo "Warming up..."
  wrk -t4 -c100 -d5s http://0.0.0.0:8000 >/dev/null 2>&1

  echo "Running benchmark..."
  wrk -t4 -c100 -d60s http://0.0.0.0:8000 > results/spring-local.txt

  lsof -t -i:8000 | xargs kill
  sleep 2
}

# ---------------------------
# Benchmark list
# format: name | directory | start command | output filename
# ---------------------------
benchmarks=(
  "mitsuki-socketify|mitsuki-socketify|python3 app.py|mitsuki-socketify-local.txt"
  "mitsuki-granian|mitsuki-granian|python3 app.py|mitsuki-granian-local.txt"
  "mitsuki-uvicorn|mitsuki-uvicorn|python3 app.py|mitsuki-uvicorn-local.txt"
  "fastapi|fastapi|python3 app.py|fastapi-local.txt"
  "starlette-uvicorn|starlette-uvicorn|python3 app.py|starlette-uvicorn-local.txt"
  "starlette-granian|starlette-granian|python3 app.py|starlette-granian-local.txt"
  "flask|flask|python3 app.py|flask-local.txt"
  "django|django|python3 app.py|django-local.txt"
  "elysia|elysia|bun app.ts|elysia-local.txt"
  "express|express|node app.js|express-local.txt"
  "gin|gin|go run app.go|gin-local.txt"
)

# ---------------------------
# Run all benchmarks
# ---------------------------
for bench in "${benchmarks[@]}"; do
  IFS="|" read -r name dir cmd outfile <<< "$bench"
  run_benchmark "$name" "$dir" "$cmd" "$outfile"
done

# Spring Boot handled separately
run_spring_boot

echo "Benchmarks finished. Results are in the 'results' directory."