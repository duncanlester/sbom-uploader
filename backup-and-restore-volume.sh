#!/bin/bash

# Backup all Docker volumes
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

# Backup Jenkins Volume
backup_jenkins() {
    echo "Starting Jenkins backup..."
    mkdir -p ~/backups
    docker-compose -f ~/dev/jenkins-validator/docker-compose.yml up -d jenkins-master
    sleep 10
    docker-compose -f ~/dev/jenkins-validator/docker-compose.yml exec -T jenkins-master tar czf /var/jenkins_home/jenkins_home_data_1.tar.gz -C /var/jenkins_home .
    docker cp jenkins-master:/var/jenkins_home/jenkins_home_data_1.tar.gz ~/backups/
    echo "Backup completed: ~/backups/jenkins_home_data_1.tar.gz"
}

# Restore Jenkins Volume
restore_jenkins() {
    echo "Starting Jenkins restore..."
    docker-compose -f ~/dev/jenkins-validator/docker-compose.yml stop jenkins-master
    docker run --rm -v jenkins_home_data_1:/jenkins_home -v ~/backups:/backup busybox sh -c "cd /jenkins_home && tar xzf /backup/jenkins_home_data_1.tar.gz"
    docker-compose -f ~/dev/jenkins-validator/docker-compose.yml up -d jenkins-master
    echo "Restore completed"
}

# Main menu
if [ "$1" == "backup" ]; then
    backup_jenkins
elif [ "$1" == "restore" ]; then
    restore_jenkins
elif [ "$1" == "backup-all" ]; then
    backup_all_volumes "${2:-}"
else
    echo "Usage: $0 [backup|restore|backup-all] [backup-dir]"
    echo "  backup      - Backup Jenkins volume to ~/backups/"
    echo "  restore     - Restore Jenkins volume from ~/backups/"
    echo "  backup-all  - Backup ALL Docker volumes (default dir: ~/backups/volumes/)"
    echo "                Optionally pass a custom backup directory as the second argument"
fi
