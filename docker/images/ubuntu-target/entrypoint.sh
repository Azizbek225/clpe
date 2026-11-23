#!/bin/sh
cat /var/log/apache2/access.log.seed >> /var/log/apache2/access.log 2>/dev/null
/usr/sbin/sshd
apachectl -D FOREGROUND
