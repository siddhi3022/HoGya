pipeline {
    agent any

    tools {
        jdk 'JDK17'
    }

    environment {
        DOCKER_IMAGE_ORDER = 'rs-sbsm-order'
        DOCKER_IMAGE_INVENTORY = 'rs-sbsm-inventory'
    }

    stages {

        stage('Checkout') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/siddhi3022/HoGya.git'

                echo 'Checked out source from GitHub branch main'
            }
        }

        stage('Verify Environment') {
            steps {
                bat 'java -version'
                bat 'python --version'
                bat 'docker --version'
                bat 'docker compose version'
            }
        }

        stage('Setup / Dependencies') {
            steps {
                bat 'python -m pip install --upgrade pip'
                bat 'python -m pip install -r requirements.txt'
            }
        }

        stage('Test / Validation') {
            steps {
                bat 'python -m compileall order-service inventory-service'
                bat 'python -m pytest -q tests'
            }
        }

        stage('Docker Build') {
            steps {
                bat 'docker compose build'
            }
        }

        stage('Docker Compose Deploy') {
            steps {
                bat 'docker compose down'
                bat 'docker compose up -d'
            }
        }

        stage('Service Verification') {
            steps {
                powershell '''
                    $order = Invoke-WebRequest -Uri "http://localhost:8001/" -UseBasicParsing
                    $inventory = Invoke-WebRequest -Uri "http://localhost:8002/" -UseBasicParsing

                    if ($order.StatusCode -ne 200) {
                        throw "Order Service verification failed."
                    }

                    if ($inventory.StatusCode -ne 200) {
                        throw "Inventory Service verification failed."
                    }

                    Write-Host "Order Service and Inventory Service are healthy."
                '''
            }
        }

        stage('Final Status') {
            steps {
                echo 'CI/CD pipeline completed successfully.'
            }
        }
    }

    post {
        always {
            bat 'docker compose ps'
            bat 'docker compose logs --tail 20'
        }

        success {
            echo 'DevOps pipeline succeeded. Microservices deployed.'
        }

        failure {
            echo 'Pipeline failed. Check Jenkins console output.'
        }
    }
}
