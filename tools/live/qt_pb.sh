#!/usr/bin/env bash

set -eou pipefail

if [[ "${EUID}" -eq 0 ]] ; then
	echo "ERROR: THIS SCRIPT MUST NOT BE RUN AS ROOT!"
	exit 1
fi

QT_PB_DIR="${HOME}/qt_pb"
QTPYVCP_DIR="${QT_PB_DIR}/qtpyvcp"
PB_DIR="${QT_PB_DIR}/probe_basic"
LINUXCNC_CONFDIR="${HOME}/linuxcnc/configs"
PB_CONFIGS=(
	"atc_sim"
	"machine_setup_files"
	"probe_basic"
	"probe_basic_asm"
	"probe_basic_lathe"
	"probe_basic_lathe_mm"
	"probe_basic_robot"
	"rack_atc_sim"
)

# Only pyside6 is supported
QT_PB_GIT_OPTS=(--depth=1 --single-branch -b pyside6)

mkdir -p "${QT_PB_DIR}"

for i in qtpyvcp probe_basic ; do
	if [[ "${i}" == "qtpyvcp" ]] ; then
		GIT_DIR="${QTPYVCP_DIR}"
	elif [[ "${i}" == "probe_basic" ]] ; then
		GIT_DIR="${PB_DIR}"
	fi

	GIT_SRC="https://github.com/kcjengr/${i}.git"

	if [[ ! -d "${GIT_DIR}" ]] ; then
		git clone "${QT_PB_GIT_OPTS[@]}" "${GIT_SRC}" "${GIT_DIR}"
	else
		cd "${GIT_DIR}"
		git clean -dxf
		git fetch origin pyside6
		git reset --hard FETCH_HEAD
	fi
done

cd "${QTPYVCP_DIR}"
python3 -m venv venv --system-site-packages
# shellcheck disable=SC1091
source "${QTPYVCP_DIR}/venv/bin/activate"

pip install --upgrade pip setuptools wheel hiyapyco \
	recommonmark

pip install -e "${QTPYVCP_DIR}"
qcompile "${QTPYVCP_DIR}"
qnative

cd "${PB_DIR}"
pip install -e "${PB_DIR}"
qcompile "${PB_DIR}"

mkdir -p "${HOME}/.local/share/fonts"

echo "Copying font for Probe Basic..."

if [[ -r "${PB_DIR}/fonts/ProbeBasicBebasMono.ttf" ]] ; then
	cp -arL "${PB_DIR}/fonts/ProbeBasicBebasMono.ttf" \
		"${HOME}/.local/share/fonts/"
else
	echo "ERROR: CANNOT FIND FONT FOR PROBE BASIC!"
	exit 1
fi

fc-cache -f

echo "Done."

touch "${HOME}/.bashrc"

if ! grep -q "source ${QTPYVCP_DIR}/venv/bin/activate" "${HOME}/.bashrc" ; then
	echo "source ${QTPYVCP_DIR}/venv/bin/activate" >> "${HOME}/.bashrc"
fi

echo "Refreshing Probe Basic configs in LinuxCNC directory..."

mkdir -p "${LINUXCNC_CONFDIR}"

for i in "${PB_CONFIGS[@]:?}" ; do
	rm -rf "${LINUXCNC_CONFDIR:?}/${i:?}"
	cp -arL "${PB_DIR}/configs/${i}" "${LINUXCNC_CONFDIR}/"
done


echo "Complete! You may now open a NEW terminal and launch LinuxCNC."
