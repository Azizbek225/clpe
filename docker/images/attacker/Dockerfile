# CLPE hujumchi (attacker) obrazi — Kali Linux asosida, asosiy pentest vositalari bilan.
# Qurish: docker build -t clpe/attacker:1.0 docker/images/attacker
FROM kalilinux/kali-rolling
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      nmap netcat-traditional curl wget iproute2 iputils-ping dnsutils \
      nikto sqlmap hydra whatweb gobuster ftp telnet openssh-client proxychains4 \
      john hashcat-utils python3 python3-requests vim-tiny less ca-certificates \
      metasploit-framework \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash student && echo 'PS1="\[\e[32m\]\u@\h\[\e[0m\]:\[\e[36m\]\w\[\e[0m\]\$ "' >> /root/.bashrc
WORKDIR /root
CMD ["sleep", "infinity"]
