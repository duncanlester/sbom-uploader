#!/bin/bash

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
else
    echo "Usage: $0 [backup|restore]"
    echo "  backup  - Backup Jenkins volume to ~/backups/"
    echo "  restore - Restore Jenkins volume from ~/backups/"
fi
