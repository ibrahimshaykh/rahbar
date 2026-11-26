# nginx-unprivileged already runs as uid 101 and listens above 1024.
FROM nginxinc/nginx-unprivileged:1.30-alpine

# The base image lags security fixes (openssl, curl, libexpat, zlib, brotli,
# nginx). It also pins nginx and its modules to exact versions in /etc/apk/world,
# so a plain `apk upgrade` skips them: drop those pins, then upgrade from Alpine
# and from nginx.org's own repository (whose signing key the base image ships).
# Then drop back to the unprivileged user below.
USER root
RUN sed -i -E 's/^(nginx[a-z0-9-]*)[=<>~].*$/\1/' /etc/apk/world \
 && apk upgrade --no-cache --repository "https://nginx.org/packages/alpine/v$(cut -d. -f1,2 /etc/alpine-release)/main"

# ui/nginx.conf listens on 8080, writes only under /tmp, and logs to stdout.
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html

USER 101

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
