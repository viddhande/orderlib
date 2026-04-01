from locust import HttpUser, task, between

class OrderlibUser(HttpUser):
    wait_time = between(0.2, 1.0)

    @task(3)
    def home(self):
        self.client.get("/")

    @task(1)
    def health(self):
        self.client.get("/health")
