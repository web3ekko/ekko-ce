.PHONY: build lint compose-up compose-down

build:
	go mod tidy
	go build -o bin/benthos ./cmd/benthos

lint:
	go vet ./...
	golangci-lint run

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

.DEFAULT_GOAL := build
