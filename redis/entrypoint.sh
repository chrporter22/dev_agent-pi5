#!/bin/sh
# ============================================================
# REDIS ENTRYPOINT — redis/entrypoint.sh
# Substitutes per-service passwords into the ACL template
# (redis.conf is mounted read-only; we write the substituted
# ACL to the same path so redis-server can load it).
# Then execs redis-server with the static config.
# ============================================================

set -eu

sed \
  -e "s#\${REDIS_PASSWORD_BOT}#${REDIS_PASSWORD_BOT}#g" \
  -e "s#\${REDIS_PASSWORD_WORKER}#${REDIS_PASSWORD_WORKER}#g" \
  -e "s#\${REDIS_PASSWORD_ML}#${REDIS_PASSWORD_ML}#g" \
  -e "s#\${REDIS_PASSWORD_NODEAPI}#${REDIS_PASSWORD_NODEAPI}#g" \
  /usr/local/etc/redis/users.acl.template \
  | grep -v '^[[:space:]]*#' \
  | grep -v '^[[:space:]]*$' \
  > /usr/local/etc/redis/users.acl

chmod 644 /usr/local/etc/redis/users.acl

exec redis-server /usr/local/etc/redis/redis.conf
