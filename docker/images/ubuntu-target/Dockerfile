# CLPE Ubuntu nishon serveri: SSH (student/student) + Apache. Blue Team lab uchun web-shell "joylashtirilgan".
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends openssh-server apache2 php libapache2-mod-php sudo iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash student && echo 'student:student' | chpasswd \
    && mkdir -p /run/sshd /var/www/html/uploads
COPY shell.php /var/www/html/uploads/shell.php
COPY access.log /var/log/apache2/access.log.seed
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 22 80
CMD ["/entrypoint.sh"]
