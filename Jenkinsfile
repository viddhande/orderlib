pipeline {
  agent { label 'slave' }

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    APP_NAME   = "orderlib"
    IMAGE_TAG  = "v${BUILD_NUMBER}"

    // SonarQube URL (change if different)
    SONAR_HOST_URL = "http://127.0.0.1:9000"

    // Nexus values stored as Jenkins Secret Text credentials
    NEXUS_DOCKER_REGISTRY = credentials('NEXUS_DOCKER_REGISTRY')  // push endpoint (often 8083)
    NEXUS_PYPI_URL        = credentials('NEXUS_PYPI_URL')
    SONAR_TOKEN           = credentials('SONAR_TOKEN')

    // Sonar scanner local install path
    SONAR_SCANNER_BIN = "${WORKSPACE}/.tools/sonar-scanner/bin/sonar-scanner"
    SONAR_SCANNER_VER = "5.0.1.3006"

    // ---- EKS / Deployment config ----
    AWS_REGION   = "ap-south-1"
    EKS_CLUSTER  = "orderlib-eks"
    K8S_NS       = "orderlib"

    // IMPORTANT: registry that Kubernetes nodes will PULL from (HTTPS endpoint)
    // Example value: 65.0.55.41:8443
    K8S_IMAGE_REGISTRY = credentials('K8S_IMAGE_REGISTRY')
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        sh '''
          set -e
          echo "User: $(whoami)"
          python3 --version
          docker --version
        '''
      }
    }

    stage('Setup venv + deps') {
      steps {
        sh '''
          set -e
          rm -rf venv dist build *.egg-info coverage.xml .pytest_cache unit-report.html || true
          python3 -m venv venv
          . venv/bin/activate
          pip install -U pip
          pip install -U build twine pytest pytest-html requests locust coverage flask
          pip install -e .
        '''
      }
    }

    stage('Install SonarScanner (if missing)') {
      steps {
        sh '''
          set -e

          if command -v sonar-scanner >/dev/null 2>&1; then
            echo "SonarScanner already available in PATH: $(command -v sonar-scanner)"
            exit 0
          fi

          echo "SonarScanner not found. Installing locally into ${WORKSPACE}/.tools ..."
          mkdir -p "${WORKSPACE}/.tools"
          cd "${WORKSPACE}/.tools"

          if ! command -v unzip >/dev/null 2>&1; then
            echo "ERROR: unzip not found on agent. Install once: sudo apt-get install -y unzip"
            exit 1
          fi

          curl -L -o sonar-scanner.zip \
            "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VER}-linux.zip"

          unzip -o sonar-scanner.zip >/dev/null
          rm -f sonar-scanner.zip

          rm -rf sonar-scanner
          mv "sonar-scanner-${SONAR_SCANNER_VER}-linux" sonar-scanner
          chmod +x "${WORKSPACE}/.tools/sonar-scanner/bin/sonar-scanner"

          "${WORKSPACE}/.tools/sonar-scanner/bin/sonar-scanner" -v
        '''
      }
    }

    stage('Build Wheel') {
      steps {
        sh '''
          set -e
          . venv/bin/activate
          python3 -m build
          ls -l dist
        '''
      }
      post {
        always { archiveArtifacts artifacts: 'dist/*', fingerprint: true }
      }
    }

    stage('Unit Tests') {
      steps {
        sh '''
          set -e
          . venv/bin/activate
          pytest -q tests/test_unit.py --disable-warnings --maxfail=1 --html=unit-report.html
        '''
      }
      post {
        always { archiveArtifacts artifacts: 'unit-report.html', fingerprint: true }
      }
    }

    stage('Functional Tests (Docker run + /health)') {
      steps {
        sh '''
          set -e
          docker rm -f orderlib-func 2>/dev/null || true

          DOCKER_BUILDKIT=0 docker build -t orderlib:func-${BUILD_NUMBER} .
          docker run -d --name orderlib-func -p 5000:5000 orderlib:func-${BUILD_NUMBER}
          sleep 6

          . venv/bin/activate
          export APP_URL=http://127.0.0.1:5000/health
          pytest -q tests/test_functional.py --disable-warnings --maxfail=1

          docker rm -f orderlib-func || true
        '''
      }
    }

    stage('Performance Tests (Locust headless)') {
      steps {
        sh '''
          set -e
          docker rm -f orderlib-perf 2>/dev/null || true
          docker run -d --name orderlib-perf -p 5000:5000 orderlib:func-${BUILD_NUMBER}
          sleep 5

          . venv/bin/activate
          locust -f performance/locustfile.py --headless -u 20 -r 5 -t 20s --host http://127.0.0.1:5000

          docker rm -f orderlib-perf || true
        '''
      }
    }

    stage('Sonar Scan') {
      steps {
        sh '''
          set -e
          . venv/bin/activate

          coverage run -m pytest -q tests/test_unit.py
          coverage xml -o coverage.xml

          if command -v sonar-scanner >/dev/null 2>&1; then
            SCANNER="sonar-scanner"
          else
            SCANNER="${SONAR_SCANNER_BIN}"
          fi

          "$SCANNER" \
            -Dsonar.projectKey=orderlib \
            -Dsonar.projectName=orderlib \
            -Dsonar.sources=app \
            -Dsonar.tests=tests \
            -Dsonar.host.url=${SONAR_HOST_URL} \
            -Dsonar.login=${SONAR_TOKEN} \
            -Dsonar.python.coverage.reportPaths=coverage.xml
        '''
      }
    }

    stage('Upload Wheel to Nexus (PyPI Hosted)') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'NEXUS_USERPASS', usernameVariable: 'NEXUS_USER', passwordVariable: 'NEXUS_PASS')]) {
          sh '''
            set -e
            set +x
            cat > ~/.pypirc <<EOP
[distutils]
index-servers = nexus

[nexus]
repository: ${NEXUS_PYPI_URL}
username: ${NEXUS_USER}
password: ${NEXUS_PASS}
EOP
            set -x

            . venv/bin/activate
            twine upload -r nexus dist/*

            rm -f ~/.pypirc
          '''
        }
      }
    }

    stage('Docker Build + Push to Nexus Docker') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'NEXUS_USERPASS', usernameVariable: 'NEXUS_USER', passwordVariable: 'NEXUS_PASS')]) {
          sh '''
            set -e
            set +x
            echo "${NEXUS_PASS}" | docker login ${NEXUS_DOCKER_REGISTRY} -u "${NEXUS_USER}" --password-stdin
            set -x

            DOCKER_BUILDKIT=0 docker build -t ${NEXUS_DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG} .
            docker push ${NEXUS_DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG}
          '''
        }
      }
    }

    // -------------------------------
    // NEW: Deploy to EKS (CD)
    // -------------------------------
    stage('Configure kubeconfig for EKS') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'AWS_CREDS']]) {
          sh '''
            set -e
            aws --version
            kubectl version --client=true

            # Write kubeconfig for Jenkins runtime user
            aws eks update-kubeconfig --region ${AWS_REGION} --name ${EKS_CLUSTER}

            kubectl get nodes
          '''
        }
      }
    }

    stage('Deploy to EKS (kubectl apply)') {
      steps {
        sh '''
          set -e

          # Apply manifests from repo (you created k8s/ folder)
          kubectl apply -f k8s/namespace.yaml
          kubectl apply -f k8s/service.yaml
          kubectl apply -f k8s/deployment.yaml

          # Ensure we deploy the image tag that Jenkins just pushed
          # IMPORTANT: K8S_IMAGE_REGISTRY should be HTTPS registry that nodes can pull from
          kubectl -n ${K8S_NS} set image deployment/${APP_NAME} \
            ${APP_NAME}=${K8S_IMAGE_REGISTRY}/${APP_NAME}:${IMAGE_TAG} --record=true

          kubectl -n ${K8S_NS} rollout status deployment/${APP_NAME} --timeout=180s
          kubectl -n ${K8S_NS} get pods -o wide
          kubectl -n ${K8S_NS} get svc -o wide
        '''
      }
    }
  }

  post {
    always {
      sh 'docker system prune -af || true'
    }
  }
}
