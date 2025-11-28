FROM golang:1.25-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY app.go .

# Compile the application.
# -o app: names the output file 'app'
# -ldflags -s -w: reduces the binary size by removing debugging symbols
# CGO_ENABLED=0: creates a statically linked binary, making it easy to run on minimal base images
RUN CGO_ENABLED=0 go build -o app -ldflags "-s -w" app.go

FROM scratch

ENV PORT 8000
EXPOSE 8000

COPY --from=builder /app/app .

CMD ["/app"]