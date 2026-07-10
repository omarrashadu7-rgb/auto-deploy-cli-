pipeline {
    agent any

    environment {
        IMAGE_NAME = "autodeploy-app"
        IMAGE_TAG = "${BUILD_NUMBER}"
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

        stage('Verify Image') {
            steps {
                sh 'docker images'
            }
        }

        stage('Deploy Container') {
            steps {
                sh '''
                docker rm -f autodeploy-container || true

                docker run -d \
                --name autodeploy-container \
                -p 5000:5000 \
                ${IMAGE_NAME}:${IMAGE_TAG}
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                sleep 10
                curl http://localhost:5000
                '''
            }
        }
    }
}
