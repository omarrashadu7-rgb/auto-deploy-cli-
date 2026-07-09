pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo 'Cloning Repository...'
            }
        }

        stage('Build Docker Image') {
            steps {
                sh 'docker build -t autodeploy-app ./test-app'
            }
        }

        stage('List Images') {
            steps {
                sh 'docker images'
            }
        }
    }
}

