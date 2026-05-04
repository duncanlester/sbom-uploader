# Docker Swarm Setup Instructions

Follow these steps to set up your DependencyTrack stack with Docker Swarm on your deployment machine.

## Prerequisites
- Docker Engine installed on your deployment machine
- The `docker-compose.yml` and `borgmatic-config.yaml` files copied to the deployment machine
- Your secret files: `db_password` and `admin_password`

## Step 1: Initialize Docker Swarm

```bash
docker swarm init
```

**Output will look like:**
```
Swarm initialized: current node (xxxxx) is now a manager.

To add a worker to this swarm, run the following command:

    docker swarm join --token SWMTKN-1-xxxxx <manager-ip>:2377
```

If you want to add additional nodes (workers) later, use the command provided above.

## Step 2: Create Docker Secrets

From the directory containing your secret files, run:

```bash
# Create database password secret
docker secret create db_password - < ./db_password

# Create admin password secret
docker secret create admin_password - < ./admin_password
```

Verify secrets were created:
```bash
docker secret ls
```

You should see both `admin_password` and `db_password` listed.

## Step 3: Set Environment Variables

Create a `.env` file in your deployment directory (if not already present):

```bash
# PostgreSQL Configuration
POSTGRES_PASSWORD=<your_postgres_password>

# LDAP / Active Directory Configuration
LDAP_SERVER_URL=ldaps://<your-ldap-server>:636
LDAP_BASEDN=dc=example,dc=com
LDAP_BIND_USERNAME=cn=svc-dtrack,ou=ServiceAccounts,dc=example,dc=com
LDAP_BIND_PASSWORD=<your_ldap_password>
LDAP_AUTH_USERNAME_FORMAT=%s@example.com
LDAP_ATTRIBUTE_NAME=userPrincipalName
LDAP_ATTRIBUTE_MAIL=mail
LDAP_GROUPS_BASEDN=ou=Groups,dc=example,dc=com
LDAP_GROUPS_FILTER=(& (objectClass=group)(objectCategory=Group))
LDAP_USER_GROUPS_FILTER=(member: 1.2.840.113556.1.4.1941:={USER_DN})

# Borgmatic Backup Configuration
BORG_PASSPHRASE=<your_borg_passphrase>
```

## Step 4: Create External Networks and Volumes

```bash
# Create the Docker network
docker network create --driver overlay dtrack-network

# Create the volumes
docker volume create dtrack_postgres_data
docker volume create dtrack_apiserver_data
docker volume create swagger
```

## Step 5: Set Up the NFS/SMB Mount for Backups

Mount your network backup share to `/mnt/borg-repository`:

**For NFS:**
```bash
sudo mount -t nfs <nfs-server>:<nfs-path> /mnt/borg-repository
```

**For SMB/CIFS:**
```bash
sudo mount -t cifs //<smb-server>/<share> /mnt/borg-repository -o username=<user>,password=<pass>
```

To make this permanent, add to `/etc/fstab` and mount with:
```bash
sudo mount -a
```

## Step 6: Deploy the Stack

```bash
docker stack deploy -c docker-compose.yml dtrack
```

## Step 7: Verify Deployment

Check stack status:
```bash
docker stack ls
docker stack services dtrack
docker stack ps dtrack
```

Check service logs:
```bash
docker service logs dtrack_postgres
docker service logs dtrack_dependency-track-apiserver
```

## Common Commands

**View all services:**
```bash
docker service ls
```

**Scale a service:**
```bash
docker service scale dtrack_dependency-track-apiserver=2
```

**Update environment variables:**
```bash
docker service update --env-add NEW_VAR=value dtrack_postgres
```

**Restart a service:**
```bash
docker service update --force dtrack_postgres
```

**View service logs:**
```bash
docker service logs dtrack_<service_name>
```

**Remove the entire stack:**
```bash
docker stack rm dtrack
```

## Secrets Management

**View all secrets:**
```bash
docker secret ls
```

**Update a secret:**
```bash
# Remove the old secret
docker secret rm db_password

# Create the new secret
docker secret create db_password - < ./new_db_password

# Force service restart to use new secret
docker service update --force dtrack_postgres
docker service update --force dtrack_borgmatic
```

## Troubleshooting

**Services won't start:**
- Check logs: `docker service logs dtrack_<service_name>`
- Verify networks exist: `docker network ls`
- Verify volumes exist: `docker volume ls`

**Borgmatic not backing up:**
- Verify NFS/SMB mount: `ls /mnt/borg-repository`
- Check borgmatic logs: `docker service logs dtrack_borgmatic`
- Verify secret: `docker secret inspect db_password`

**Networking issues:**
- Ensure overlay network is created: `docker network create --driver overlay dtrack-network`
- Verify services can communicate: `docker exec <container_id> ping postgres`
