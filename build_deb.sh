#!/bin/bash
set -e
APP_NAME="chemtox-profiler"
VERSION="1.1.2"
ARCH="all"

if [ ! -d "build_deb/${APP_NAME}_${VERSION}" ]; then
    echo "Ошибка: сначала запустите ./prepare_deb.sh"
    exit 1
fi

dpkg-deb --build --root-owner-group "build_deb/${APP_NAME}_${VERSION}" "build_deb/${APP_NAME}_${VERSION}_${ARCH}.deb"
echo "Пакет создан: build_deb/${APP_NAME}_${VERSION}_${ARCH}.deb"
