#!/bin/bash
# EC2 user-data: bootstraps the POPPy web server (nginx + static site) on first boot.
# Runs as root via cloud-init. Logs to /var/log/cloud-init-output.log on the instance.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y nginx git rsync certbot python3-certbot-nginx

# Clone the POPPy repo (public) and deploy the static site from website/
install -d /opt/poppy
if [ ! -d /opt/poppy/repo/.git ]; then
  git clone --depth 1 https://github.com/RomanoLab/poppy.git /opt/poppy/repo
fi
install -d /var/www/poppy
rsync -a --delete /opt/poppy/repo/website/ /var/www/poppy/

# nginx vhost for the site. Starts HTTP-only; `sudo poppy-tls` (below) upgrades this
# file in place to add TLS (listen 443 + cert + an 80->443 redirect) once DNS is pointed.
cat > /etc/nginx/sites-available/poppy <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name poppyontology.org www.poppyontology.org _;

    root /var/www/poppy;
    index index.html Home.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/poppy /etc/nginx/sites-enabled/poppy
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

# Redeploy helper for future site updates: `sudo poppy-deploy`
cat > /usr/local/bin/poppy-deploy <<'DEPLOY'
#!/bin/bash
set -euo pipefail
cd /opt/poppy/repo
git pull --ff-only
rsync -a --delete /opt/poppy/repo/website/ /var/www/poppy/
nginx -t && systemctl reload nginx
echo "deployed $(git rev-parse --short HEAD)"
DEPLOY
chmod +x /usr/local/bin/poppy-deploy

# TLS helper: obtain/install a Let's Encrypt cert and switch nginx to HTTPS.
# Run ONCE after DNS (A @ / A www) points at this box:  sudo poppy-tls
# certbot edits the vhost above in place (so TLS survives `poppy-deploy`) and installs
# a systemd renewal timer (certbot.timer), so renewals are automatic thereafter.
cat > /usr/local/bin/poppy-tls <<'TLS'
#!/bin/bash
set -euo pipefail
certbot --nginx -n --agree-tos --no-eff-email \
  -m joseph.romano@pennmedicine.upenn.edu \
  -d poppyontology.org -d www.poppyontology.org --redirect
nginx -t && systemctl reload nginx
echo "TLS active. Renewals are automatic (systemctl status certbot.timer)."
TLS
chmod +x /usr/local/bin/poppy-tls

echo "POPPy bootstrap complete"
echo "NEXT: point DNS (A @ / A www) at this box, then run: sudo poppy-tls"
