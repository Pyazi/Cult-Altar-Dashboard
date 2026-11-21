#!/usr/bin/env bash
# ==============================================================================
#  ♛ Cult Altar Dashboard — Linux & Steam Deck One-Line Installer
# ==============================================================================
#  Usage:
#    curl -sSL https://raw.githubusercontent.com/Pyazi/Cult-Altar-Dashboard/main/install.sh | bash
# ==============================================================================

set -euo pipefail

# --- Цвета для красивого вывода ---
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- Настройки репозитория и путей ---
GITHUB_REPO="${GITHUB_REPO:-Pyazi/Cult-Altar-Dashboard}"
INSTALL_DIR="${HOME}/.local/share/cult-altar"
APPLICATIONS_DIR="${HOME}/.local/share/applications"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_FILE="${APPLICATIONS_DIR}/cult-altar.desktop"
BIN_PATH="${INSTALL_DIR}/CultAltar-Linux"
ICON_PATH="${INSTALL_DIR}/cult_altar.ico"

echo -e "${PURPLE}${BOLD}"
echo "  ♛ ===================================================== ♛"
echo "        АЛТАРЬ УПРАВЛЕНИЯ — CULT ALTAR DASHBOARD"
echo "          Установка для Linux и Steam Deck (SteamOS)"
echo "  ♛ ===================================================== ♛"
echo -e "${NC}"

# --- Проверка наличия curl ---
if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ Ошибка: curl не установлен. Установите curl и повторите запуск.${NC}"
    exit 1
fi

# --- Создание целевых каталогов ---
echo -e "${CYAN}📁 Создание каталогов установки...${NC}"
mkdir -p "${INSTALL_DIR}"
mkdir -p "${APPLICATIONS_DIR}"
mkdir -p "${BIN_DIR}"

# --- Определение ссылки для скачивания последнего релиза ---
RELEASE_URL="https://github.com/${GITHUB_REPO}/releases/latest/download/CultAltar-Linux"
ICON_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/main/cult_altar.ico"

echo -e "${CYAN}⬇️  Скачивание CultAltar-Linux из GitHub Releases (${GITHUB_REPO})...${NC}"
if curl -sSL --fail -L -o "${BIN_PATH}" "${RELEASE_URL}"; then
    echo -e "${GREEN}✅ Исполняемый файл успешно загружен в: ${BIN_PATH}${NC}"
else
    echo -e "${YELLOW}⚠️  Не удалось скачать последний бинарный релиз напрямую.${NC}"
    echo -e "${YELLOW}Попытка обнаружения через GitHub API...${NC}"
    API_URL="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"
    DOWNLOAD_URL=$(curl -sSL "${API_URL}" | grep "browser_download_url.*CultAltar-Linux" | cut -d : -f 2,3 | tr -d '\" ' || true)
    
    if [ -n "${DOWNLOAD_URL}" ]; then
        curl -sSL -L -o "${BIN_PATH}" "${DOWNLOAD_URL}"
        echo -e "${GREEN}✅ Исполняемый файл успешно загружен через API: ${BIN_PATH}${NC}"
    else
        echo -e "${RED}❌ Не удалось найти готовый бинарник CultAltar-Linux в релизах ${GITHUB_REPO}.${NC}"
        echo -e "${YELLOW}💡 Если вы запускаете скрипт из исходников, соберите бинарник через PyInstaller или проверьте теги релизов.${NC}"
        exit 1
    fi
fi

# --- Выдача прав на исполнение ---
echo -e "${CYAN}🔑 Настройка прав доступа...${NC}"
chmod +x "${BIN_PATH}"

# --- Скачивание иконки ---
echo -e "${CYAN}🖼️  Загрузка иконки приложения...${NC}"
if [ -f "cult_altar.ico" ]; then
    cp "cult_altar.ico" "${ICON_PATH}"
else
    curl -sSL -L -o "${ICON_PATH}" "${ICON_URL}" || true
fi

# --- Создание символической ссылки в ~/.local/bin ---
if [ -d "${BIN_DIR}" ]; then
    ln -sf "${BIN_PATH}" "${BIN_DIR}/cult-altar"
    echo -e "${GREEN}✅ Создана команда запуска: ~/.local/bin/cult-altar${NC}"
fi

# --- Создание ярлыка .desktop для меню приложений и Steam ---
echo -e "${CYAN}📝 Создание ярлыка .desktop в ${DESKTOP_FILE}...${NC}"
cat <<EOF > "${DESKTOP_FILE}"
[Desktop Entry]
Type=Application
Name=Cult Altar Dashboard
GenericName=System Monitor & Remote Control
Comment=Desktop widget monitor and PC remote controller for mobile devices
Exec=${BIN_PATH}
Icon=${ICON_PATH}
Terminal=false
Categories=Utility;System;
StartupNotify=true
Keywords=cult;altar;dashboard;monitor;remote;widget;steamdeck;
EOF

chmod +x "${DESKTOP_FILE}"

# Обновляем базу данных меню приложений, если утилита доступна
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "${APPLICATIONS_DIR}" &> /dev/null || true
fi

echo -e "${GREEN}${BOLD}"
echo "🎉 УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!"
echo -e "${NC}"
echo -e "📍 Каталог установки: ${BLUE}${INSTALL_DIR}${NC}"
echo -e "🚀 Ярлык приложения: ${BLUE}${DESKTOP_FILE}${NC}"
echo ""
echo -e "${YELLOW}${BOLD}🎮 Инструкция для Steam Deck (SteamOS):${NC}"
echo -e "  1. В ${BOLD}Desktop Mode${NC} откройте клиент Steam."
echo -e "  2. В меню выберите: ${CYAN}Игры (Games) → Добавить стороннюю игру в мою библиотеку...${NC}"
echo -e "  3. Отметьте галочкой ${BOLD}«Cult Altar Dashboard»${NC} и нажмите «Добавить выбранные»."
echo -e "  ${PURPLE}ИЛИ${NC} просто запустите Алтарь, перейдите в ${BOLD}«⚙️ Настройки»${NC} и нажмите кнопку:"
echo -e "  ${GREEN}«🎮 Добавить в игровой режим Steam»${NC} (он автоматически пропишет игру в shortcuts.vdf)."
echo ""
echo -e "${YELLOW}${BOLD}💡 Полезные команды:${NC}"
echo -e "  • Обычный запуск (GUI):        ${CYAN}${BIN_PATH}${NC}"
echo -e "  • Фоновый запуск без GUI:      ${CYAN}${BIN_PATH} --headless${NC}"
echo -e "  • Если ~/.local/bin в PATH:    ${CYAN}cult-altar${NC}"
echo ""
echo -e "${GREEN}Приятного использования Алтаря Управления! 🔥${NC}"
