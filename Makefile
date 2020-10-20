SHELL := /bin/bash
PWD := $(shell pwd)

GIT_REMOTE = github.com/7574-sistemas-distribuidos/docker-compose-init

default: build

all:

deps:
	go mod tidy
	go mod vendor

build: deps
	GOOS=linux go build -o bin/client github.com/7574-sistemas-distribuidos/docker-compose-init/client
.PHONY: build

docker-image:
	docker build -f ./server/Dockerfile -t "server:latest" .
	docker build -f ./client/Dockerfile -t "client:latest" .
.PHONY: docker-image

docker-compose-up: docker-image
	docker volume create --name DataVolume1
	docker-compose -f docker-compose-dev.yaml up -d --build
.PHONY: docker-compose-up

docker-compose-down:
	docker-compose -f docker-compose-dev.yaml stop -t 1
	docker-compose -f docker-compose-dev.yaml down
.PHONY: docker-compose-down

docker-compose-logs:
	docker-compose -f docker-compose-dev.yaml logs -f
.PHONY: docker-compose-logs

new-server:
	docker run -e CLI_ID=$(NAME) -e CLI_SERVER_ADDRESS=server:12345 --rm --name $(NAME) --entrypoint /client --net 7574-tp1_testing_net -v DataVolume1:/datavolume1 client:latest
.PHONY: new-server

client-register-node:
	echo "admin-reg $(NODE) $(PORT) $(NODE_PATH) $(FREQ)" | docker run -i --network=7574-tp1_testing_net busybox nc server 12345
.PHONY: client-register-node

new-content-creator:
	./content_creator.sh name1 a/file1.txt &
.PHONY: new-server

init-content-creators:
	./content_creator.sh name1 a/file1.txt &
	./content_creator.sh name2 a/file2.txt &
	./content_creator.sh name3 b/file1.txt &
.PHONY: init-content-creators

kill-content-creators:
	docker kill name1
	docker kill name2
	docker kill name3
.PHONY: kill-content-creators
