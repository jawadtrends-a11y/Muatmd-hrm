#!/usr/bin/env bash
# ══════════ حساب SFTP لجهاز بصمة شركة (ق-٨٥ · ق-٢٧٠) ══════════
#
# ⚠️⚠️ **الجهاز يرفع ولا يدخل.** جهاز BioTime يصدّر ملفّاته دوريًّا عبر SFTP
# فيحتاج حسابًا بكلمة مرور — **والنظام يمنع دخول SSH بكلمة مرور** (ق-٢٦٤).
# فيُقيَّد الحساب بثلاثة:
#   ١ **`internal-sftp` وحده** — لا صدفة ولا أمر
#   ٢ **`ChrootDirectory`** — لا يرى إلا مجلّده
#   ٣ **مجموعة `biotime`** — فالاستثناء لها وحدها لا لكل المستخدمين
#
# ⚠️ **ولا يُنشئه النظام بنفسه**: إنشاء مستخدمٍ يحتاج root، وفتحُ بابٍ من
# الحاوية إلى نظام التشغيل ثغرةٌ أخطر ممّا يحلّ. فالشركة تُسجّل جهازها،
# ويصل المشرفَ طلبٌ، ويُشغّل هذا بيده.
#
# الاستعمال:  sudo bash scripts/add_biotime_sftp.sh <company_id>
set -euo pipefail

CID="${1:-}"
[[ "$CID" =~ ^[0-9]+$ ]] || { echo "الاستعمال: $0 <company_id>"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "⚠️ يحتاج root — استعمل sudo"; exit 1; }

USER="bt${CID}"
HOME_DIR="/srv/biotime/${USER}"

# ⚠️ **جذر الـchroot ملكُ root**: يشترط SSH ألّا يملكه المستخدم وإلا رفض
# الاتصال. فيكتب في `upload` وحده، والنظام ينقل لـ`archive` (ق-٤٤).
mkdir -p "${HOME_DIR}/upload" "${HOME_DIR}/archive"
chown root:root "${HOME_DIR}"
chmod 755 "${HOME_DIR}"

getent group biotime > /dev/null || groupadd biotime
id "$USER" > /dev/null 2>&1 || \
  useradd -g biotime -d "$HOME_DIR" -s /usr/sbin/nologin "$USER"

chown "$USER":biotime "${HOME_DIR}/upload" "${HOME_DIR}/archive"
chmod 770 "${HOME_DIR}/upload" "${HOME_DIR}/archive"

CONF=/etc/ssh/sshd_config.d/70-biotime-sftp.conf
if [ ! -f "$CONF" ]; then
  cat > "$CONF" << 'CONFEOF'
# ⚠️ أجهزة البصمة وحدها — بكلمة مرور وبـSFTP مقيَّد.
# (وكلمة مرور SSH ممنوعةٌ لبقيّة المستخدمين: ق-٢٦٤.)
Match Group biotime
    PasswordAuthentication yes
    ChrootDirectory %h
    ForceCommand internal-sftp -d /upload
    AllowTcpForwarding no
    X11Forwarding no
CONFEOF
  sshd -t && { systemctl reload ssh 2>/dev/null || systemctl reload sshd; }
  echo "✔ أُضيف إعداد SFTP لمجموعة biotime"
fi

PASS="$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 20)"
echo "${USER}:${PASS}" | chpasswd
cat << EOT
════════════════════════════════════════
 الشركة    : ${CID}
 المستخدم  : ${USER}
 كلمة المرور: ${PASS}
 المنفذ    : 22 (SFTP)
 المجلّد    : /upload
 ⚠️ انسخها الآن — لا تُعرض ثانيةً
════════════════════════════════════════
EOT
