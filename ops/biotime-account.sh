#!/usr/bin/env bash
# ينشئ حساب SFTP لشركة تستقبل ملفات BioTime (ق-85).
#
# يُنفَّذ على الخادم لا داخل الحاوية: إنشاء المستخدمين شأن نظام
# التشغيل، والحاوية لا تعرف مجموعات الخادم.
#
#   ./ops/biotime-account.sh <company_id>
set -euo pipefail

COMPANY_ID="${1:?معرّف الشركة مطلوب}"
USER="bt${COMPANY_ID}"
HOME_DIR="/srv/biotime/${USER}"

# الحبس يشترط أن يملك المجلد root وألا يكتب فيه غيره
mkdir -p "${HOME_DIR}"
chown root:root "${HOME_DIR}"
chmod 755 "${HOME_DIR}"

if ! id -u "${USER}" >/dev/null 2>&1; then
  useradd -M -d "${HOME_DIR}" -s /usr/sbin/nologin -g sftpusers "${USER}"
fi

PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
echo "${USER}:${PASSWORD}" | chpasswd

for d in upload archive; do
  mkdir -p "${HOME_DIR}/${d}"
  chown "${USER}:sftpusers" "${HOME_DIR}/${d}"
  chmod 775 "${HOME_DIR}/${d}"
done

HOST="$(curl -s -4 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"

cat <<INFO

حساب SFTP لشركة رقم ${COMPANY_ID}

  المضيف:       ${HOST}
  المنفذ:       22
  المستخدم:     ${USER}
  كلمة المرور:  ${PASSWORD}
  مسار الرفع:   /upload

اضبطها في BioTime: النظام ← إعدادات ← إعدادات FTP
واختر SFTP إن كان متاحًا.

احفظ كلمة المرور — لا تُعرض مرة أخرى.

INFO
