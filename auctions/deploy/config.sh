#!/usr/bin/env bash
# Несекретные параметры стенда. Пароли здесь НЕ хранятся.
APP_IP=172.16.248.10
DB_IP=172.16.248.11
INTERNAL_IF=enp26s0          # host-only интерфейс
APP_PORT=8000
APP_USER=auctions            # системный пользователь, от которого работает приложение
APP_DIR=/opt/auctions
REPO_URL=https://github.com/nice1ce/auctions
DB_NAME=auctions
DB_APP_ROLE=auctions_app
DB_MIGRATOR_ROLE=auctions_migrator
ENV_FILE=/etc/auctions/auctions.env
