#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Запускайте через sudo"; exit 1; }

ADMIN=${1:?usage: sudo ./01-ssh-hardening.sh <admin_user>}
KEYS=/home/$ADMIN/.ssh/authorized_keys

# Защита от потери доступа: без ключа пароли не отключаем
[[ -s $KEYS ]] || { echo "Нет $KEYS. Сначала: ssh-copy-id $ADMIN@<host>"; exit 1; }

# 00-, чтобы файл читался раньше файлов установщика (в sshd побеждает первое значение)
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<EOF
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers $ADMIN
EOF

sshd -t
systemctl reload ssh
sshd -T | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication|allowusers)'
