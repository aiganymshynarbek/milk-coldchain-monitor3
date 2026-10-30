// CI/CD pipeline for coldchain-monitor.
// Runs on every new commit (SCM polling), tests the code inside Docker,
// builds the image, smoke-tests it, optionally pushes it to Docker Hub and
// deploys it to a staging container (CD).
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    triggers {
        // Check the Git repository every ~2 minutes and build when there is a new commit.
        // (A GitHub webhook can replace polling when Jenkins has a public URL.)
        pollSCM('H/2 * * * *')
    }

    parameters {
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false,
                     description: 'Push the image to Docker Hub (needs the "dockerhub" credentials)')
        string(name: 'DOCKERHUB_REPO', defaultValue: 'your-dockerhub-user/coldchain-monitor',
               description: 'Docker Hub repository for the push stage')
        booleanParam(name: 'DEPLOY_STAGING', defaultValue: true,
                     description: 'Deploy the new image to the staging container on port 8000')
    }

    environment {
        IMAGE = 'coldchain-monitor'
        TAG = "${env.BUILD_NUMBER}"
        TEST_CONTAINER = "coldchain-test-${env.BUILD_NUMBER}"
        STAGING = 'coldchain-staging'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log -1 --pretty=format:"%h %an: %s"'
            }
        }

        stage('Unit tests') {
            steps {
                sh 'docker build --target test -t ${IMAGE}-test:${TAG} .'
                sh 'docker run --name ${TEST_CONTAINER} ${IMAGE}-test:${TAG}'
            }
            post {
                always {
                    sh '''
                        rm -rf reports
                        docker cp ${TEST_CONTAINER}:/app/reports ./reports || true
                        docker rm -f ${TEST_CONTAINER} || true
                    '''
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                    archiveArtifacts artifacts: 'reports/*.xml', allowEmptyArchive: true
                }
            }
        }

        stage('Build image') {
            steps {
                sh 'docker build --target runtime -t ${IMAGE}:${TAG} -t ${IMAGE}:latest .'
                sh 'docker image ls ${IMAGE}'
            }
        }

        stage('Smoke test') {
            steps {
                sh 'docker run --rm ${IMAGE}:${TAG} coldchain --version'
                sh 'docker run --rm ${IMAGE}:${TAG} coldchain forecast data/example_log.csv --hours 3'
            }
        }

        stage('Push to Docker Hub') {
            when { expression { params.PUSH_IMAGE } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub',
                                                  usernameVariable: 'DH_USER',
                                                  passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker tag ${IMAGE}:${TAG} ${DOCKERHUB_REPO}:${TAG}
                        docker tag ${IMAGE}:${TAG} ${DOCKERHUB_REPO}:latest
                        docker push ${DOCKERHUB_REPO}:${TAG}
                        docker push ${DOCKERHUB_REPO}:latest
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to staging') {
            when { expression { params.DEPLOY_STAGING } }
            steps {
                sh '''
                    docker rm -f ${STAGING} || true
                    docker run -d --name ${STAGING} --restart unless-stopped -p 8000:8000 ${IMAGE}:${TAG}
                    for i in 1 2 3 4 5 6 7 8 9 10; do
                        if docker exec ${STAGING} python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health', timeout=2).read().decode())" 2>/dev/null; then
                            exit 0
                        fi
                        sleep 2
                    done
                    echo "staging did not become healthy"; docker logs ${STAGING}; exit 1
                '''
            }
        }
    }

    post {
        success {
            echo "Build ${env.BUILD_NUMBER} passed: image ${env.IMAGE}:${env.TAG}"
        }
        failure {
            echo "Build ${env.BUILD_NUMBER} failed - see the stage logs above"
        }
        always {
            sh 'docker image rm ${IMAGE}-test:${TAG} || true'
        }
    }
}
