#!/bin/bash
# Single volume
#./backup-and-restore-volume.sh backup jenkins_home_data_1
#./backup-and-restore-volume.sh restore jenkins_home_data_1

# All volumes
#./backup-and-restore-volume.sh backup-all
#./backup-and-restore-volume.sh restore-all

# Optional custom backup dir as last argument for all commands
# ./backup-and-restore-volume.sh backup my_volume /mnt/nas/backups
# Backup all Docker volumes to <backup_dir>/<volume_name>.tar.gz

backup_all_volumes() {
    local backup_dir="${1:-$HOME/backups/volumes}"
    mkdir -p "$backup_dir"
    echo "Backing up all Docker volumes to $backup_dir..."

    local volumes
    volumes=$(docker volume ls --quiet)

    if [ -z "$volumes" ]; then
        echo "No Docker volumes found."
        return
    fi

    for volume in $volumes; do
        echo "  Backing up volume: $volume"
        docker run --rm \
            -v "$volume":/data \
            -v "$backup_dir":/backup \
            alpine \
            tar -czf "/backup/${volume}.tar.gz" -C /data .
        echo "  Saved: $backup_dir/${volume}.tar.gz"
    done

    echo "All volumes backed up to $backup_dir"
}

# Restore all volumes from .tar.gz files in <backup_dir>
# Creates each volume if it does not already exist on this host
restore_all_volumes() {
    local backup_dir="${1:-$HOME/backups/volumes}"

    if [ ! -d "$backup_dir" ]; then
        echo "Backup directory not found: $backup_dir"
        exit 1
    fi

    local archives
    archives=$(find "$backup_dir" -maxdepth 1 -name "*.tar.gz")

    if [ -z "$archives" ]; then
        echo "No .tar.gz backup files found in $backup_dir"
        exit 1
    fi

    for archive in $archives; do
        local filename
        filename=$(basename "$archive")
        local volume="${filename%.tar.gz}"

        # Create the volume if it doesn't exist (safe on a fresh Docker host)
        if ! docker volume inspect "$volume" > /dev/null 2>&1; then
            echo "  Creating volume: $volume"
            docker volume create "$volume"
        else
            echo "  Volume already exists, overwriting data: $volume"
        fi

        echo "  Restoring $volume from $archive"
        docker run --rm \
            -v "$volume":/data \
            -v "$backup_dir":/backup \
            alpine \
            sh -c "tar -xzf /backup/${filename} -C /data"
        echo "  Restored: $volume"
    done

    echo "All volumes restored from $backup_dir"
}

# Backup a single named volume to <backup_dir>/<volume_name>.tar.gz
backup_volume() {
    local volume="$1"
    local backup_dir="${2:-$HOME/backups/volumes}"

    if [ -z "$volume" ]; then
        echo "Error: volume name required"
        echo "Usage: $0 backup <volume_name> [backup-dir]"
        exit 1
    fi

    if ! docker volume inspect "$volume" > /dev/null 2>&1; then
        echo "Error: volume '$volume' does not exist"
        exit 1
    fi

    mkdir -p "$backup_dir"
    echo "Backing up volume '$volume' to $backup_dir/${volume}.tar.gz..."
    docker run --rm \
        -v "$volume":/data \
        -v "$backup_dir":/backup \
        alpine \
        tar -czf "/backup/${volume}.tar.gz" -C /data .
    echo "Saved: $backup_dir/${volume}.tar.gz"
}

# Restore a single named volume from <backup_dir>/<volume_name>.tar.gz
restore_volume() {
    local volume="$1"
    local backup_dir="${2:-$HOME/backups/volumes}"

    if [ -z "$volume" ]; then
        echo "Error: volume name required"
        echo "Usage: $0 restore <volume_name> [backup-dir]"
        exit 1
    fi

    local archive="$backup_dir/${volume}.tar.gz"
    if [ ! -f "$archive" ]; then
        echo "Error: backup file not found: $archive"
        exit 1
    fi

    if ! docker volume inspect "$volume" > /dev/null 2>&1; then
        echo "Creating volume: $volume"
        docker volume create "$volume"
    else
        echo "Volume already exists, overwriting data: $volume"
    fi

    echo "Restoring '$volume' from $archive..."
    docker run --rm \
        -v "$volume":/data \
        -v "$backup_dir":/backup \
        alpine \
        sh -c "tar -xzf /backup/${volume}.tar.gz -C /data"
    echo "Restored: $volume"
}

if [ "$1" == "backup-all" ]; then
    backup_all_volumes "${2:-}"
elif [ "$1" == "restore-all" ]; then
    restore_all_volumes "${2:-}"
elif [ "$1" == "backup" ]; then
    backup_volume "${2:-}" "${3:-}"
elif [ "$1" == "restore" ]; then
    restore_volume "${2:-}" "${3:-}"
else
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "  backup <volume>  [backup-dir]  - Backup a single volume"
    echo "  restore <volume> [backup-dir]  - Restore a single volume"
    echo "  backup-all       [backup-dir]  - Backup ALL Docker volumes"
    echo "  restore-all      [backup-dir]  - Restore ALL volumes from backup dir"
    echo ""
    echo "  Default backup dir: ~/backups/volumes/"
    echo "  Volumes are created automatically if they don't exist on restore."
fi
