#!/bin/sh
# Wrapper entrypoint that reads Docker Swarm secrets and passes them as environment variables

# Read database password from secret
if [ -f /run/secrets/db_password ]; then
    export ALPINE_DATABASE_PASSWORD=$(cat /run/secrets/db_password)
fi

# Read LDAP bind password from secret
if [ -f /run/secrets/ldap_bind_password ]; then
    export ALPINE_LDAP_BIND_PASSWORD=$(cat /run/secrets/ldap_bind_password)
fi

# Execute the original command passed to the container
exec "$@"
