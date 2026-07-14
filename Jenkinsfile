pipeline {
    agent any

    environment {
        APP_NAME       = "auto-deploy-app"
        IMAGE_NAME     = "auto-deploy-app"
        IMAGE_TAG      = "${BUILD_NUMBER}"
        ROLLBACK_TAG   = "rollback"
        CONTAINER_NAME = "auto-deploy-app-container"
        APP_PORT       = "5000"
        HOST_PORT      = "5000"
        HEALTH_URL     = "http://localhost:${HOST_PORT}/health"
        HEALTH_RETRIES = "5"
        HEALTH_DELAY   = "3"
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        stage('Checkout') {
            steps {
                echo "Checking out source code..."
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
                dir('test-app') {
                    sh "docker build \
			-t ${IMAGE_NAME}:${IMAGE_TAG} \
			-t ${IMAGE_NAME}:latest \ 
			."
                }
            }
        }

        stage('Backup Current Container') {
            steps {
                script {
                    def runningImage = sh(
                        script: "docker inspect --format='{{.Config.Image}}' ${CONTAINER_NAME} 2>/dev/null || true",
                        returnStdout: true
                    ).trim()

                    if (runningImage) {
                        echo "Backing up current image '${runningImage}' as rollback candidate..."
                        sh "docker tag ${runningImage} ${IMAGE_NAME}:${ROLLBACK_TAG}"
                        env.ROLLBACK_AVAILABLE = "true"
                    } else {
                        echo "No running container found. Skipping rollback backup."
                        env.ROLLBACK_AVAILABLE = "false"
                    }
                }
            }
        }

        stage('Deploy New Version') {
            steps {
                echo "Deploying new container from ${IMAGE_NAME}:${IMAGE_TAG}"
                sh """
                    docker stop ${CONTAINER_NAME} || true
                    docker rm ${CONTAINER_NAME} || true
                    docker run -d \
			docker run -d \
			--name ${CONTAINER_NAME} \
			-e APP_VERSION=${IMAGE_TAG} \
			-p ${HOST_PORT}:${APP_PORT} \
			${IMAGE_NAME}:${IMAGE_TAG}
                """
            }
        }

        stage('Health Check') {
            steps {
                script {
                    echo "Running health check against ${HEALTH_URL}"
                    def healthy = false

                    for (int i = 1; i <= env.HEALTH_RETRIES.toInteger(); i++) {
                        def status = sh(
                            script: "curl -s -o /dev/null -w '%{http_code}' ${HEALTH_URL} || true",
                            returnStdout: true
                        ).trim()

                        echo "Attempt ${i}/${HEALTH_RETRIES} - HTTP status: ${status}"

                        if (status.startsWith("2")) {
                            healthy = true
                            break
                        }
                        sleep(env.HEALTH_DELAY.toInteger())
                    }

                    env.DEPLOY_HEALTHY = healthy.toString()

                    if (!healthy) {
                        error("Health check failed after ${env.HEALTH_RETRIES} attempts.")
                    }
                }
            }
        }
    }

    post {
        failure {
            script {
                echo "Deployment failed. Initiating rollback procedure..."

                if (env.ROLLBACK_AVAILABLE == "true") {
                    sh """
                        docker stop ${CONTAINER_NAME} || true
                        docker rm ${CONTAINER_NAME} || true
                        docker run -d \
                            --name ${CONTAINER_NAME} \
                            --restart unless-stopped \
                            -p ${HOST_PORT}:${APP_PORT} \
                            ${IMAGE_NAME}:${ROLLBACK_TAG}
                    """
                    echo "Rollback completed. Previous stable version restored."
                } else {
                    echo "No previous version available. Rollback skipped."
                }
            }
        }
        success {
            echo "Deployment successful. Application is healthy and running on port ${HOST_PORT}."
            echo "Active image: ${IMAGE_NAME}:${IMAGE_TAG}"
        }
        always {
            sh "docker image prune -f || true"
        }
    }
}
