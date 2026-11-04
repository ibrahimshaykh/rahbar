# nginx-unprivileged already runs as uid 101 and listens above 1024.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# ui/nginx.conf listens on 8080, writes only under /tmp, and logs to stdout.
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html

USER 101

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
