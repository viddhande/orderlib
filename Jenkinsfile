pipeline {
  agent { label 'slave' }   // ensure your Jenkins agent node has label: slave

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    APP_NAME   = "orderlib"
    IMAGE_TAG  = "v${BUILD_NUMBER}"

    // SonarQube URL (SonarQube container is on same SLAVE host)
    SONAR_HOST_URL = "http://127.0.0.1:9000"

    // Enable BuildKit (removes legacy builder warning)
    DOCKER_BUILDKIT = "1"

    // Credentials stored in Jenkins:
    NEXUS_DOCKER_REGISTRY = credentials('NEXUS_DOCKER_REGISTRY')  // e.g. 65.0.55.41:8083
    NEXUS_PYPI_URL        = credentials('NEXUS_PYPI_URL')         // e.g. http://65.0.55.41:8081/repository/pypi-hosted/
    SONAR_TOKEN           = credentials('SONAR_TOKEN')

    // Workspace-local SonarScanner path (we will install if missing)
    SONAR_SCANNER_BIN = "${WORKSPACE}/.tools/sonar-scanner/bin/sonar-scanner"
    SONAR_SCANNER_VER = "5.0.1.3006"
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

          # If system sonar-scanner exists, good. Otherwise install to workspace.
          if command -v sonar-scanner >/dev/null 2>&1; then
            echo "SonarScanner already available in PATH: $(command -v sonar-scanner)"
            exit 0
          fi

          # Workspace-local install (no sudo required)
          echo "SonarScanner not found. Installing locally into ${WORKSPACE}/.tools ..."
          mkdir -p "${WORKSPACE}/.tools"
          cd "${WORKSPACE}/.tools"

          # Ensure unzip exists (should be installed on agent once)
          if ! command -v unzip >/dev/null 2>&1; then
            echo "ERROR: unzip not found on agent. Install once: sudo apt-get install -y unzip"
            exit 1
          fi

          curl -L -o sonar-scanner.zip \
            "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SONAR_SCANNER_VER}-linux.zip"

          unzip -o sonar-scanner.zip >/dev/null
          rm -f sonar-scanner.zip

          # Normalize folder name
          rm -rf sonar-scanner
          mv "sonar-scanner-${SONAR_SCANNER_VER}-linux" sonar-scanner

          chmod +x "${WORKSPACE}/.tools/sonar-scanner/bin/sonar-scanner"

          echo "Installed SonarScanner at: ${WORKSPACE}/.tools/sonar-scanner/bin/sonar-scanner"
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
        always {
          archiveArtifacts artifacts: 'dist/*', fingerprint: true
        }
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
        always {
          archiveArtifacts artifacts: 'unit-report.html', fingerprint: true
        }
      }
    }

    stage('Functional Tests (Docker run + /health)') {
      steps {
        sh '''
          set -e
          docker rm -f orderlib-func || true
          docker build -t orderlib:func-${BUILD_NUMBER} .
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
          docker rm -f orderlib-perf || true
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

          # Coverage report for SonarQube
          coverage run -m pytest -q tests/test_unit.py
          coverage xml -o coverage.xml

          # Use system sonar-scanner if present, else use workspace-local
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
            # Create pypirc temporarily (do not commit it)
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

            docker build -t ${NEXUS_DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG} .
            docker push ${NEXUS_DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG}
          '''
        }
      }
    }
  }

  post {
    always {
      // Keep this if disk is limited; otherwise change to "docker system prune -f"
      sh 'docker system prune -af || true'
    }
  }
}
