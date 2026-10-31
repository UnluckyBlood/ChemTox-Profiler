#!/bin/bash
set -e

APP_NAME="chemtox-profiler"
VERSION="1.1.2"
ARCH="all"
INSTALL_DIR="/opt/${APP_NAME}"
BUILD_DIR="build_deb/${APP_NAME}_${VERSION}"

rm -rf build_deb
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}${INSTALL_DIR}"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/share/applications"

cp -r db start.py streamlit_app.py requirements.txt "${BUILD_DIR}${INSTALL_DIR}/" 2>/dev/null || true

cat > "${BUILD_DIR}/usr/bin/${APP_NAME}" << 'LAUNCHER'
#!/bin/bash
INSTALL_DIR="/opt/chemtox-profiler"
VENV_DIR="${INSTALL_DIR}/venv"
exec "$VENV_DIR/bin/streamlit" run "${INSTALL_DIR}/streamlit_app.py" --server.headless=false
LAUNCHER
chmod 755 "${BUILD_DIR}/usr/bin/${APP_NAME}"

cat > "${BUILD_DIR}/usr/share/applications/${APP_NAME}.desktop" << 'DESKTOP'
[Desktop Entry]
Name=ChemTox Profiler
Comment=Прогнозирование токсичности
Exec=chemtox-profiler
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Science;Chemistry;
DESKTOP

cat > "${BUILD_DIR}/DEBIAN/control" << CONTROL
Package: ${APP_NAME}
Version: ${VERSION}
Section: science
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-venv, python3-pip, libgl1, curl, git
Maintainer: Your Name <you@example.com>
Description: ChemTox Profiler
CONTROL

cat > "${BUILD_DIR}/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e
INSTALL_DIR="/opt/chemtox-profiler"
VENV_DIR="${INSTALL_DIR}/venv"

echo "Настройка ChemTox Profiler (поиск Python 3.12)..."

# 1. Ищем Python 3.12 в системе
if command -v python3.12 &>/dev/null; then
    PY312=$(command -v python3.12)
else
    # 2. Если нет, ставим pyenv для текущего пользователя и через него Python 3.12
    echo "Python 3.12 не найден. Установка локального Python 3.12..."
    if [ ! -d "/home/$SUDO_USER/.pyenv" ]; then
        sudo -u $SUDO_USER curl -sL https://pyenv.run | sudo -u $SUDO_USER bash
    fi
    sudo -u $SUDO_USER /home/$SUDO_USER/.pyenv/bin/pyenv install -s 3.12.12
    PY312="/home/$SUDO_USER/.pyenv/versions/3.12.12/bin/python3.12"
fi

rm -rf "$VENV_DIR"
"$PY312" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

mkdir -p "${INSTALL_DIR}/eskape_output"
chmod -R 777 "${INSTALL_DIR}"
echo "Установка завершена."
POSTINST
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

cat > "${BUILD_DIR}/DEBIAN/postrm" << 'POSTRM'
#!/bin/bash
set -e
rm -rf "/opt/chemtox-profiler/venv"
POSTRM
chmod 755 "${BUILD_DIR}/DEBIAN/postrm"

echo "Структура пакета готова."
