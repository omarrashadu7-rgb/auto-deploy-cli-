pipeline {
    agent any

    environment {
        IMAGE_NAME = "autodeploy-app"
        IMAGE_TAG = "${BUILD_NUMBER}"
        CONTAINER_NAME = "autodeploy-container"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                docker build \
                -t ${IMAGE_NAME}:${IMAGE_TAG} \
                ./test-app
                '''
            }
        }

        stage('Backup Current Version') {
            steps {
                sh '''
                docker inspect ${CONTAINER_NAME} >/dev/null 2>&1 && \
                docker commit ${CONTAINER_NAME} rollback-image:latest || true
                '''
            }
        }

        stage('Deploy New Version') {
            steps {
                sh '''
                docker rm -f ${CONTAINER_NAME} || true

                docker run -d \
                  --name ${CONTAINER_NAME} \
                  -p 5000:5000 \
                  ${IMAGE_NAME}:${IMAGE_TAG}
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                sleep 10

                curl -f http://localhost:5000
                '''
            }
        }
    }

    post {

        success {
            echo "Deployment Successful"
        }

        failure {
            echo "Deployment Failed - Starting Rollback"

            sh '''
            docker rm -f ${CONTAINER_NAME} || true

            docker run -d \
              --name ${CONTAINER_NAME} \
              -p 5000:5000 \
              rollback-image:latest || true
            '''
        }
    }
}
